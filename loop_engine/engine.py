"""The loop. Domain-agnostic. ~100 lines. This is the reusable core — don't rebuild it.

    plan -> act -> observe -> verify -> (correct & repeat | succeed | give up)

The engine calls the Adapter's plan/act/verify, emits a glass-box trace, and keeps looping
until verify() returns no violations or it hits max_iters. When verify finds violations it
feeds them back into the next plan() as `history` — that feedback is the "self-correct".
"""
from __future__ import annotations

from dataclasses import dataclass

from .adapter import Adapter, State
from .trace import Trace


@dataclass
class LoopResult:
    success: bool
    iterations: int
    state: State
    trace: Trace
    violations: list[str]  # remaining violations if it gave up


class LoopEngine:
    def __init__(self, adapter: Adapter, max_iters: int = 6, trace: Trace | None = None):
        self.adapter = adapter
        self.max_iters = max_iters
        self.trace = trace or Trace()

    def run(self, goal: str, initial_data: dict | None = None) -> LoopResult:
        state = State(goal=goal, data=dict(initial_data or {}))
        t = self.trace
        violations: list[str] = []

        iters_done = 0
        for i in range(1, self.max_iters + 1):
            iters_done = i
            # --- PLAN: decide the next action, informed by prior failures ---
            plan = self.adapter.plan(state)
            t.emit("PLAN", i, plan)

            # --- ACT: do it ---
            state = self.adapter.act(plan, state)
            t.emit("ACT", i, f"applied: {plan[:80]}",
                   **{k: _short(v) for k, v in state.data.items() if k.startswith("_show_")})

            # Extension: an adapter can abort the loop (e.g. policy denies every
            # remaining remediation) — falls through to FAIL so callers escalate.
            if state.data.get("_abort"):
                violations = [str(state.data["_abort"])]
                break

            # --- OBSERVE + VERIFY: check against a real oracle ---
            t.emit("OBSERVE", i, "checking result against the verify oracle…")
            violations = self.adapter.verify(state)

            if not violations:
                t.emit("SUCCESS", i, "verify passed — no violations. Loop complete.")
                state.history.append(f"iter {i}: SUCCESS")
                return LoopResult(True, i, state, t, [])

            # --- CORRECT: record the violations so the next plan() fixes them ---
            t.emit("VERIFY", i, f"{len(violations)} violation(s) found",
                   violations=violations)
            if i < self.max_iters:
                t.emit("CORRECT", i, "feeding violations back into the next plan — self-correcting")
            state.history.append(
                f"iter {i}: attempted '{plan[:60]}' -> violations: {violations}"
            )

        t.emit("FAIL", iters_done,
               f"gave up after {iters_done} iteration(s) with {len(violations)} violation(s)",
               violations=violations)
        return LoopResult(False, iters_done, state, t, violations)


def _short(v: object, n: int = 100) -> str:
    s = str(v)
    return s if len(s) <= n else s[: n - 1] + "…"
