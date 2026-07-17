"""Golden-path rehearsal stopwatch. Boots the server, watches the SSE stream, and
grades the run against the demo script beats + the hard <=90s wall-clock budget.

    .venv/bin/python -m sentinel.rehearse              # online (uses key if set)
    .venv/bin/python -m sentinel.rehearse --offline    # cached/deterministic plans

PASS requires, measured from feed start:
  - seeded disk_full RESOLVED with iterations == 2 (the visible self-correction)
  - a policy-BLOCKED action followed by a NEEDS_HUMAN audit for db_lock
  - heartbeats keep flowing after the last incident (the feed never looks canned)
  - total feed-start -> final audit <= 90s
Exit code 0 only on PASS. The printed detect->fix time is the DEMO.md closing number.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

PORT = 8788
BASE = f"http://127.0.0.1:{PORT}"
BUDGET_S = 90.0


def main() -> int:
    offline = "--offline" in sys.argv
    env = dict(os.environ)
    env.update({"SENTINEL_PORT": str(PORT), "SENTINEL_START_DELAY": "2"})
    if offline:
        env["SENTINEL_OFFLINE"] = "1"

    # A lingering server from a prior run would feed us a REPLAYED (already-finished)
    # story and wreck the stopwatch — refuse to measure against a dirty port.
    try:
        urllib.request.urlopen(f"{BASE}/healthz", timeout=1)
        print(f"FATAL: something is already serving on :{PORT} — kill it first.")
        return 2
    except Exception:
        pass

    srv = subprocess.Popen(
        [sys.executable, "-m", "sentinel.app"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    beats: dict[str, float] = {}
    audits: list[dict] = []
    plans: list[str] = []
    hb_after_last_audit = 0
    t_feed = None
    mode = "OFFLINE" if offline else "online"
    print(f"=== rehearsal ({mode}) — waiting for server… ===")
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(f"{BASE}/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("server never came up"); return 2

        resp = urllib.request.urlopen(f"{BASE}/events", timeout=180)
        deadline = time.time() + 150
        for raw in resp:
            if time.time() > deadline:
                print("watchdog: run exceeded 150s"); return 2
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue
            d = json.loads(line[6:])
            ch = d.get("channel")
            if ch == "feed":
                ev = d["event"]
                if t_feed is None and "feed online" in ev["summary"]:
                    t_feed = time.time()
                    beats["feed start"] = 0.0
                elif ev["severity"] == "incident" and t_feed:
                    beats[f"detect {ev['type']}"] = time.time() - t_feed
                elif audits and ev["kind"] == "heartbeat":
                    hb_after_last_audit += 1
            elif ch == "loop" and t_feed:
                key = f"{d['step'].lower()} {d['event_id']}"
                if d["step"] in ("CORRECT", "SUCCESS", "FAIL") and key not in beats:
                    beats[key] = time.time() - t_feed
                if d["step"] == "PLAN":
                    plans.append(d["message"])
            elif ch == "action" and d.get("blocked") and t_feed:
                beats.setdefault("POLICY BLOCKED", time.time() - t_feed)
            elif ch == "audit" and t_feed:
                audits.append(d)
                beats[f"audit {d['incident']} -> {d['outcome']} "
                      f"({d['elapsed_s']}s detect->done)"] = time.time() - t_feed
                if len(audits) == 2:
                    # let the feed prove it keeps scrolling after the story ends
                    end_by = time.time() + 4
                    while time.time() < end_by:
                        more = resp.readline().decode().strip()
                        if more.startswith("data: "):
                            m = json.loads(more[6:])
                            if (m.get("channel") == "feed"
                                    and m["event"]["kind"] == "heartbeat"):
                                hb_after_last_audit += 1
                    break
    finally:
        srv.kill()      # hard kill: graceful shutdown can linger on our own open SSE
        srv.wait(timeout=10)

    print(f"\n--- beats (s after feed start, {mode}) ---")
    for k, v in beats.items():
        print(f"  {v:6.1f}s  {k}")
    print("\n--- plan() provenance ---")
    for p in plans:
        src = "MODEL" if "→ executing" in p else "deterministic/cached"
        print(f"  [{src}] {p[:110]}")

    total = max(v for v in beats.values())
    disk = next((a for a in audits if a["incident"] == "disk_full"), None)
    lock = next((a for a in audits if a["incident"] == "db_lock"), None)
    checks = {
        "disk_full RESOLVED in exactly 2 iterations (visible self-correction)":
            bool(disk and disk["outcome"] == "RESOLVED" and disk["iterations"] == 2),
        "db_lock BLOCKED by policy then NEEDS_HUMAN":
            bool(lock and lock["outcome"] == "NEEDS_HUMAN"
                 and any(a["blocked"] for a in lock["actions"])
                 and "POLICY BLOCKED" in beats),
        "feed keeps scrolling after final audit":
            hb_after_last_audit >= 2,
        f"golden path <= {BUDGET_S:.0f}s (was {total:.1f}s)":
            total <= BUDGET_S,
    }
    ok = all(checks.values())
    print()
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    if disk:
        print(f"\n  closing number ({mode}): disk_full detect -> verified fix "
              f"in {disk['elapsed_s']}s, zero human intervention")
    print(f"\n=== {'PASS' if ok else 'FAIL'} ({mode}) ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
