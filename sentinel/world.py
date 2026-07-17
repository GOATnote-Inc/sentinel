"""Simulated infrastructure — the ground truth SENTINEL observes and mutates.

This is the "actual condition" behind every event: incidents mutate this state, tools
remediate it, and verify() RE-INSPECTS it (state re-inspection, not model vibes).
Deterministic on purpose: the seeded incident is engineered so the runbook's first
remediation is insufficient, forcing a visible self-correction on attempt two.
"""
from __future__ import annotations

import threading

DISK_THRESHOLD = 90.0   # % — alert + violation above this
ERR_THRESHOLD = 2.0     # % of requests
QUEUE_THRESHOLD = 1000  # jobs
CERT_MIN_DAYS = 14
LAG_THRESHOLD_S = 60


class World:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.services: dict[str, dict] = {
            "checkout-api": {"class": "app", "disk_pct": 61.0, "err_rate": 0.4},
            "billing-db": {"class": "prod-db", "locked": False, "repl_lag_s": 2},
            "api-gateway": {"class": "edge", "err_rate": 0.5, "deploy": "v418"},
            "worker-pool": {"class": "app", "queue_depth": 140},
            "edge-proxy": {"class": "edge", "cert_days": 41},
            "metaview-sync": {"class": "integration", "failed_deliveries": 0},
        }

    def get(self, service: str) -> dict:
        with self._lock:
            return dict(self.services[service])

    def set(self, service: str, **kv) -> None:
        with self._lock:
            self.services[service].update(kv)

    def adjust(self, service: str, key: str, delta: float, floor: float = 0.0) -> float:
        with self._lock:
            v = max(floor, self.services[service][key] + delta)
            self.services[service][key] = v
            return v


# ---------------------------------------------------------------------------
# Incident catalog: how each incident type breaks the world, how verify()
# re-inspects it, and the runbook ladder of remediations (in escalation order).
# ---------------------------------------------------------------------------

def _disk_check(w: World, s: str) -> list[str]:
    pct = w.get(s)["disk_pct"]
    if pct > DISK_THRESHOLD:
        return [f"disk usage on {s} is {pct:.0f}% (threshold {DISK_THRESHOLD:.0f}%)"]
    return []


def _lock_check(w: World, s: str) -> list[str]:
    st = w.get(s)
    out = []
    if st["locked"]:
        out.append(f"{s} has a stuck exclusive lock; writes are queueing")
    if st["repl_lag_s"] > LAG_THRESHOLD_S:
        out.append(f"replication lag {st['repl_lag_s']}s (threshold {LAG_THRESHOLD_S}s)")
    return out


def _err_check(w: World, s: str) -> list[str]:
    r = w.get(s)["err_rate"]
    return [f"error rate on {s} is {r:.1f}% (threshold {ERR_THRESHOLD:.1f}%)"] if r > ERR_THRESHOLD else []


def _queue_check(w: World, s: str) -> list[str]:
    d = w.get(s)["queue_depth"]
    return [f"queue depth on {s} is {d} jobs (threshold {QUEUE_THRESHOLD})"] if d > QUEUE_THRESHOLD else []


def _cert_check(w: World, s: str) -> list[str]:
    d = w.get(s)["cert_days"]
    return [f"TLS cert on {s} expires in {d} days (minimum {CERT_MIN_DAYS})"] if d < CERT_MIN_DAYS else []


def _delivery_check(w: World, s: str) -> list[str]:
    n = w.get(s)["failed_deliveries"]
    return [f"{n} interview-transcript deliveries failed on {s}"] if n > 0 else []


INCIDENTS: dict[str, dict] = {
    # SEEDED two-attempt incident: rotate_logs frees only 3% (archives share the
    # partition) -> 91% still > 90% threshold -> self-correct -> purge frees 25%.
    "disk_full": {
        "service": "checkout-api",
        "trigger": lambda w: w.set("checkout-api", disk_pct=94.0),
        "check": _disk_check,
        "ladder": ["rotate_logs", "purge_archived_logs"],
        "summary": "DiskAlert: checkout-api /var/log at 94% (threshold 90%)",
        "metric": lambda w: f"disk {w.get('checkout-api')['disk_pct']:.0f}%",
    },
    # OUT-OF-POLICY incident: the only remediation is restart_service on a prod-db,
    # which the policy gate denies -> BLOCKED -> NEEDS HUMAN escalation.
    "db_lock": {
        "service": "billing-db",
        "trigger": lambda w: w.set("billing-db", locked=True, repl_lag_s=480),
        "check": _lock_check,
        "ladder": ["restart_service"],
        "summary": "DBAlert: billing-db stuck exclusive lock, repl lag 480s",
        "metric": lambda w: f"lag {w.get('billing-db')['repl_lag_s']}s",
    },
    # Ad-hoc catalog for unscripted Q&A injections:
    "error_rate_spike": {
        "service": "api-gateway",
        "trigger": lambda w: w.set("api-gateway", err_rate=14.2, deploy="v419"),
        "check": _err_check,
        "ladder": ["rollback_deploy"],
        "summary": "ErrorBudget: api-gateway 5xx at 14.2% since deploy v419",
        "metric": lambda w: f"err {w.get('api-gateway')['err_rate']:.1f}%",
    },
    "queue_backlog": {
        "service": "worker-pool",
        "trigger": lambda w: w.set("worker-pool", queue_depth=8400),
        "check": _queue_check,
        "ladder": ["scale_consumers"],
        "summary": "QueueAlert: worker-pool backlog 8,400 jobs and climbing",
        "metric": lambda w: f"depth {w.get('worker-pool')['queue_depth']}",
    },
    "cert_expiring": {
        "service": "edge-proxy",
        "trigger": lambda w: w.set("edge-proxy", cert_days=3),
        "check": _cert_check,
        "ladder": ["renew_cert"],
        "summary": "CertAlert: edge-proxy TLS cert expires in 3 days",
        "metric": lambda w: f"{w.get('edge-proxy')['cert_days']}d left",
    },
    # Metaview-flavored recruiting-ops event (simulated, labeled as such in DEMO.md).
    "interview_pipeline": {
        "service": "metaview-sync",
        "trigger": lambda w: w.set("metaview-sync", failed_deliveries=3),
        "check": _delivery_check,
        "ladder": ["replay_webhook"],
        "summary": "RecruitingOps: 3 interview-transcript deliveries failed (metaview-sync)",
        "metric": lambda w: f"{w.get('metaview-sync')['failed_deliveries']} failed",
    },
}
