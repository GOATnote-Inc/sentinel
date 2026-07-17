"""The live event feed — SENTINEL's senses.

live mode: events are delivered through Nexla (polling a Nexla-managed destination).
local mode: an in-process generator with the SAME event shape.

The feed is CONTINUOUS: routine heartbeats with randomized inter-arrival times scroll
before/during/after incidents. Scripted demo timeline: the seeded two-attempt incident
fires ~5s after feed start; the out-of-policy incident at ~60s. Ad-hoc incidents can be
injected at any time (judge Q&A) through the same path.
"""
from __future__ import annotations

import asyncio
import itertools
import random
import time

from . import config
from .bus import Bus
from .world import INCIDENTS, World

_ids = itertools.count(101)

_HEARTBEATS = [
    ("checkout-api", "health ok · p95 {n}ms", (80, 240)),
    ("api-gateway", "traffic {n} rps · 5xx nominal", (900, 2400)),
    ("billing-db", "replica sync ok · lag {n}s", (1, 4)),
    ("worker-pool", "queue depth {n} · consumers 8/8", (90, 260)),
    ("edge-proxy", "tls handshake p50 {n}ms", (11, 38)),
    ("metaview-sync", "interview-transcript sync ok · {n} delivered this hour", (2, 9)),
    ("checkout-api", "cpu {n}% · mem steady", (22, 61)),
    ("api-gateway", "deploy watcher: steady on v418 · {n} pods", (6, 12)),
]


def make_event(kind: str, itype: str | None, service: str, summary: str,
               adhoc: bool = False) -> dict:
    return {
        "id": f"evt-{next(_ids)}",
        "ts": time.time(),
        "kind": kind,                  # heartbeat | incident
        "type": itype or "heartbeat",
        "service": service,
        "severity": "incident" if kind == "incident" else "info",
        "summary": summary,
        "adhoc": adhoc,
        "detected_ts": time.time(),    # instrumentation t0: the moment it hit the feed
    }


def fire_incident(itype: str, world: World, adhoc: bool = False) -> dict:
    spec = INCIDENTS[itype]
    spec["trigger"](world)  # break the world FIRST — the event describes real state
    return make_event("incident", itype, spec["service"], spec["summary"], adhoc=adhoc)


async def run_feed(bus: Bus, world: World, enqueue) -> None:
    """Continuous heartbeats + the two scripted demo incidents."""
    t0 = time.monotonic()
    scripted = [(config.SEEDED_INCIDENT_AT, "disk_full"),
                (config.BLOCKED_INCIDENT_AT, "db_lock")]
    pending = sorted(scripted)
    bus.publish("feed", event=make_event("heartbeat", None, "sentinel",
                                         "feed online — watching 6 services"))
    while True:
        now = time.monotonic() - t0
        while pending and now >= pending[0][0]:
            _, itype = pending.pop(0)
            ev = fire_incident(itype, world)
            bus.publish("feed", event=ev)
            await enqueue(ev)
            now = time.monotonic() - t0
        svc, tmpl, (lo, hi) = random.choice(_HEARTBEATS)
        hb = make_event("heartbeat", None, svc, tmpl.format(n=random.randint(lo, hi)))
        bus.publish("feed", event=hb)
        delay = random.uniform(0.8, 2.1)
        if pending:
            delay = min(delay, max(0.05, pending[0][0] - (time.monotonic() - t0)))
        await asyncio.sleep(delay)
