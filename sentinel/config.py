"""Runtime flags. Every sponsor integration flips live<->local via env var, no code change."""
from __future__ import annotations

import os
import sys


def _mode(name: str) -> str:
    v = os.environ.get(name, "local").strip().lower()
    return v if v in ("live", "local") else "local"


NEXLA = _mode("SENTINEL_NEXLA")          # data-delivery layer for the event feed
ZERO = _mode("SENTINEL_ZERO")            # tool execution layer for act()
POMERIUM = _mode("SENTINEL_POMERIUM")    # policy gate in front of every tool call
AKASH = _mode("SENTINEL_AKASH")          # where the agent+UI run (label only; deploy is separate)

OFFLINE = (os.environ.get("SENTINEL_OFFLINE", "") == "1"
           or "--offline" in sys.argv)                     # never call the model API
FAST = os.environ.get("SENTINEL_FAST", "") == "1"         # compressed timeline for pipe tests

MODEL_ID = os.environ.get("SENTINEL_MODEL", "claude-haiku-4-5-20251001")
MODEL_TIMEOUT_S = float(os.environ.get("SENTINEL_MODEL_TIMEOUT", "10"))

PORT = int(os.environ.get("SENTINEL_PORT", "8787"))

# Pomerium live mode: registry calls route through this proxy; its PPL policy makes
# the allow/deny decision OUTSIDE the process (403 => BLOCKED verdict via Pomerium).
POMERIUM_PROXY = os.environ.get("SENTINEL_POMERIUM_PROXY", "http://localhost:8443")

# Seconds between glass-box steps so the loop is readable from the back of the room.
# Elapsed-time instrumentation includes this — the closing number stays honest.
STEP_PACE_S = float(os.environ.get("SENTINEL_STEP_PACE", "0.8"))
START_DELAY_S = float(os.environ.get("SENTINEL_START_DELAY", "6"))

# Demo timeline (seconds after feed start). FAST compresses for pipe testing only.
SEEDED_INCIDENT_AT = 3.0 if FAST else 5.0
BLOCKED_INCIDENT_AT = 12.0 if FAST else 60.0


def label(mode: str, live_name: str) -> str:
    """Honest pane label: the live service name, or 'local fallback'."""
    return live_name if mode == "live" else f"{live_name} (local fallback)"
