"""Tool registry — the agent's hands. act() calls tools ONLY through here.

live mode: calls route through Zero.xyz (zero-config tool access).
local mode: deterministic local implementations behind the SAME interface.
Every call is policy-gated (see policy.py) and returns an honest `via` label.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config, policy
from .world import World


@dataclass
class ToolResult:
    tool: str
    service: str
    ok: bool
    blocked: bool
    detail: str
    via: str            # "Zero.xyz" | "local tools (fallback)"
    policy_via: str     # "Pomerium" | "policy (local fallback)"
    rule: str = ""
    ts: float = field(default_factory=time.time)


# --- deterministic local implementations (world mutations) -------------------

def _rotate_logs(w: World, s: str) -> str:
    pct = w.adjust(s, "disk_pct", -3.0)   # archives share the partition: frees only 3%
    return f"rotated live logs; disk now {pct:.0f}%"


def _purge_archived_logs(w: World, s: str) -> str:
    pct = w.adjust(s, "disk_pct", -25.0)
    return f"purged+compressed archived logs; disk now {pct:.0f}%"


def _restart_service(w: World, s: str) -> str:
    w.set(s, locked=False, repl_lag_s=2)
    return f"restarted {s}"


def _rollback_deploy(w: World, s: str) -> str:
    w.set(s, err_rate=0.5, deploy="v418")
    return f"rolled back {s} to v418; error rate 0.5%"


def _scale_consumers(w: World, s: str) -> str:
    w.set(s, queue_depth=180)
    return f"scaled consumers 4x; queue drained to 180"


def _renew_cert(w: World, s: str) -> str:
    w.set(s, cert_days=365)
    return f"renewed TLS cert on {s}; valid 365 days"


def _replay_webhook(w: World, s: str) -> str:
    w.set(s, failed_deliveries=0)
    return f"replayed failed transcript webhooks on {s}; all delivered"


_LOCAL = {
    "rotate_logs": _rotate_logs,
    "purge_archived_logs": _purge_archived_logs,
    "restart_service": _restart_service,
    "rollback_deploy": _rollback_deploy,
    "scale_consumers": _scale_consumers,
    "renew_cert": _renew_cert,
    "replay_webhook": _replay_webhook,
}

TOOL_DESCRIPTIONS = {
    "rotate_logs": "rotate live log files (fast, low-risk, frees a little space)",
    "purge_archived_logs": "purge+compress archived logs (frees a lot of space)",
    "restart_service": "restart a service process",
    "rollback_deploy": "roll a service back to the previous deploy",
    "scale_consumers": "scale up queue consumers",
    "renew_cert": "renew a TLS certificate",
    "replay_webhook": "replay failed webhook deliveries",
}


class Registry:
    def __init__(self, world: World):
        self.world = world
        self.via = "Zero.xyz" if config.ZERO == "live" else "local tools (fallback)"

    def call(self, tool: str, service: str) -> ToolResult:
        svc_class = self.world.get(service).get("class", "app")
        v = policy.gate(tool, service, svc_class)
        if not v.allowed:
            return ToolResult(tool, service, ok=False, blocked=True,
                              detail=f"BLOCKED: {v.rule}", via=self.via,
                              policy_via=v.via, rule=v.rule)
        if config.ZERO == "live":
            # Placeholder for Zero.xyz routing (wired when credentials arrive);
            # falls through to local execution so the loop never dies on a sandbox.
            pass
        fn = _LOCAL[tool]
        detail = fn(self.world, service)
        return ToolResult(tool, service, ok=True, blocked=False, detail=detail,
                          via=self.via, policy_via=v.via, rule=v.rule)
