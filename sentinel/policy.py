"""Policy gate — EVERY tool call passes through here before it can touch the world.

live mode: the check is fronted by Pomerium (identity-aware proxy) on the tool endpoint.
local mode: the same allow/deny rules enforced in-process. The verdict shape is identical,
so the UI labels honestly flip between "POMERIUM" and "policy (local fallback)".
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config

# Deny rules, checked first. The agent physically cannot restart / fail over a
# production database — that class of action always requires a human.
DENY = [
    {"tools": {"restart_service", "failover"}, "service_class": "prod-db",
     "rule": "no service restarts on prod-db class without human approval"},
]

ALLOWED_TOOLS = {
    "rotate_logs", "purge_archived_logs", "restart_service", "rollback_deploy",
    "scale_consumers", "renew_cert", "replay_webhook",
}


@dataclass
class Verdict:
    allowed: bool
    rule: str
    via: str  # "Pomerium" | "policy (local fallback)"


def gate(tool: str, service: str, service_class: str) -> Verdict:
    via = "Pomerium" if config.POMERIUM == "live" else "policy (local fallback)"
    if tool not in ALLOWED_TOOLS:
        return Verdict(False, f"tool '{tool}' is not in the allowlist", via)
    for d in DENY:
        if tool in d["tools"] and service_class == d["service_class"]:
            return Verdict(False, d["rule"], via)
    return Verdict(True, "allowed by policy", via)
