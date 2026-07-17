"""SENTINEL server: feed -> serial incident queue -> loop_engine -> SSE glass box.

Run from hackathon/starter-kit:   .venv/bin/python -m sentinel.app
Autonomy: the feed starts by itself a few seconds after boot — there is NO run button.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from loop_engine.engine import LoopEngine
from loop_engine.model import Model
from loop_engine.trace import Trace
from skins.ops_skin import OpsAdapter

from . import config
from .bus import Bus, sse_format
from .feed import fire_incident, run_feed
from .registry import Registry
from .world import INCIDENTS, World

MAX_ITERS = 3  # retry cap; exhausting it (or a policy abort) escalates NEEDS HUMAN

bus = Bus()
world = World()
registry = Registry(world)
incident_q: asyncio.Queue[dict] = asyncio.Queue()
queued_view: list[dict] = []   # what the UI shows as "waiting"

# Claude phrases plan() (fast model, short prompts). --offline or a missing key
# degrades to deterministic cached plans — and the UI label says so honestly.
_model = Model(live=(False if config.OFFLINE else None), model=config.MODEL_ID)


def status_payload() -> dict:
    return {
        "feed": config.label(config.NEXLA, "Nexla"),
        "tools": "Zero.xyz" if config.ZERO == "live" else "local tools (fallback)",
        "policy": "Pomerium" if config.POMERIUM == "live" else "policy (local fallback)",
        "runtime": "Akash" if config.AKASH == "live" else "localhost",
        "model": (f"{config.MODEL_ID} (live)" if _model.live
                  else "offline cache (deterministic plans)"),
        "offline": config.OFFLINE,
    }


async def enqueue(ev: dict) -> None:
    queued_view.append({"id": ev["id"], "type": ev["type"], "service": ev["service"]})
    bus.publish("queue", queued=list(queued_view))
    await incident_q.put(ev)


def _run_loop_blocking(ev: dict) -> tuple:
    """Runs in a worker thread: the whole plan/act/observe/verify/correct loop."""
    trace = Trace(color=False)

    def sink(e):
        bus.publish("loop", event_id=ev["id"], step=e.step, iteration=e.iteration,
                    message=e.message, data=e.data)
        time.sleep(config.STEP_PACE_S)  # stage pacing (worker thread; feed unaffected)

    trace.sink = sink
    adapter = OpsAdapter(ev["type"], ev, world, registry, model=_model,
                         emit_meta=lambda ch, d: bus.publish(ch, **d))
    engine = LoopEngine(adapter, max_iters=MAX_ITERS, trace=trace)
    result = engine.run(goal=f"Resolve {ev['type']} on {ev['service']}: {ev['summary']}")
    return result, adapter


async def worker() -> None:
    """SERIAL queue: one incident at a time; the UI shows the rest waiting."""
    while True:
        ev = await incident_q.get()
        if queued_view and queued_view[0]["id"] == ev["id"]:
            queued_view.pop(0)
        bus.publish("queue", queued=list(queued_view))
        bus.publish("incident_start", event=ev)

        result, adapter = await asyncio.to_thread(_run_loop_blocking, ev)

        elapsed = time.time() - ev["detected_ts"]
        state = result.state
        needs_human = (not result.success) or state.data.get("needs_human", False)
        blocked_tools = state.data.get("blocked_tools", [])
        outcome = "NEEDS_HUMAN" if needs_human else "RESOLVED"
        if needs_human:
            bus.stats["needs_human"] += 1
        else:
            bus.stats["resolved"] += 1
            bus.stats["elapsed"].append(elapsed)
            bus.stats["last_elapsed_s"] = round(elapsed, 1)  # verified fixes only
        if blocked_tools:
            bus.stats["blocked"] += 1

        bus.publish(
            "audit",
            outcome=outcome,
            event_id=ev["id"],
            incident=ev["type"],
            service=ev["service"],
            trigger=ev["summary"],
            iterations=result.iterations,
            actions=[{"tool": a["tool"], "via": a["via"], "blocked": a["blocked"],
                      "policy_via": a["policy_via"], "detail": a["detail"]}
                     for a in state.data.get("actions", [])],
            verification=("verify PASSED — re-inspected "
                          f"{INCIDENTS[ev['type']]['metric'](world)}"
                          if not needs_human else
                          f"UNRESOLVED: {'; '.join(result.violations) or 'retry cap exhausted'}"),
            elapsed_s=round(elapsed, 1),
            stats=dict(bus.stats),
        )
        incident_q.task_done()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    bus.attach(asyncio.get_running_loop())
    bus.publish("status", **status_payload())
    tasks = [asyncio.create_task(worker())]

    async def delayed_feed():
        await asyncio.sleep(config.START_DELAY_S)
        await run_feed(bus, world, enqueue)

    tasks.append(asyncio.create_task(delayed_feed()))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(lifespan=lifespan)
STATIC = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/events")
async def events():
    q = bus.subscribe()

    async def stream():
        try:
            yield sse_format({"channel": "status", **status_payload()})
            while True:
                item = await q.get()
                yield sse_format(item)
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.post("/inject/{itype}")
async def inject(itype: str):
    """Ad-hoc incident (judge Q&A): same pipeline as the scripted ones."""
    if itype not in INCIDENTS:
        return JSONResponse({"error": f"unknown type; try {sorted(INCIDENTS)}"}, 404)
    ev = fire_incident(itype, world, adhoc=True)
    bus.publish("feed", event=ev)
    await enqueue(ev)
    return {"injected": ev["id"], "type": itype}


@app.post("/toolexec/{tool}/{service}")
async def toolexec(tool: str, service: str):
    """Upstream tool endpoint that Pomerium fronts in live mode. Defense in depth:
    the in-process gate ALSO runs here, so a direct hit can't bypass policy —
    Pomerium is the outer enforcement layer, this is the inner one."""
    from . import policy as _policy
    if service not in world.services or tool not in _policy.ALLOWED_TOOLS:
        return JSONResponse({"error": "unknown tool/service"}, 404)
    v = _policy.gate(tool, service, world.get(service).get("class", "app"))
    if not v.allowed:
        return JSONResponse({"ok": False, "blocked": True, "rule": v.rule}, 403)
    from .registry import _LOCAL
    detail = _LOCAL[tool](world, service)
    return {"ok": True, "detail": detail}


@app.get("/state")
async def state():
    return {"world": {s: world.get(s) for s in world.services}, "status": status_payload()}


@app.get("/healthz")
async def healthz():
    return {"ok": True, **status_payload()}


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
