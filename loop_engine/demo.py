"""Runnable proof that the engine self-corrects. Offline by default.

    python3 -m loop_engine.demo          # deterministic mock — no key needed
    python3 -m loop_engine.demo --live   # routes the PLAN step through Claude (needs ANTHROPIC_API_KEY)

The scenario is a stand-in for Day 1's "fix the failing tests" loop: the agent implements a
function, its first attempt has a bug, the verify oracle (the tests) catches it, and the loop
SELF-CORRECTS on the next iteration. That recovery is the moment you engineer for on stage.
"""
from __future__ import annotations

import sys

from .adapter import State
from .engine import LoopEngine
from .model import Model
from .trace import Trace

# The "spec": three behaviors the implementation must get right (our test suite).
REQUIRED = {"returns_sum", "handles_empty", "handles_negative"}


class DemoAdapter:
    """A deterministic dev-loop skin: implement a function, get caught, self-correct.

    `state.data["impl"]` maps behavior -> correct? . verify() returns the failing behaviors,
    exactly like a test runner returning failing test names.
    """

    name = "demo-dev-loop"

    def __init__(self, model: Model):
        self.model = model

    def plan(self, state: State) -> str:
        failing = state.data.get("_last_failing", [])
        if not state.data.get("impl"):
            intent = "Implement sum(nums): return the total; the tests cover empty and negative inputs."
        else:
            intent = f"Previous attempt failed these tests: {failing}. Fix exactly those."
        # When --live, let Claude phrase the plan (shows real model integration in the trace);
        # the deterministic act/verify below keep the demo reliable regardless of phrasing.
        if self.model.live:
            intent = self.model.complete(
                system="You are a terse coding agent. One sentence: state your next fix.",
                prompt=intent, max_tokens=60,
            ).strip() or intent
        return intent

    def act(self, plan: str, state: State) -> State:
        impl: dict[str, bool] = dict(state.data.get("impl") or {})
        if not impl:
            # First attempt: a realistic bug — forgets the negative-number case.
            impl = {"returns_sum": True, "handles_empty": True, "handles_negative": False}
        else:
            # Self-correction: fix whatever the tests flagged last round.
            for beh in state.data.get("_last_failing", []):
                impl[beh] = True
        state.data["impl"] = impl
        state.data["_show_impl"] = {k: ("ok" if v else "BUG") for k, v in impl.items()}
        return state

    def verify(self, state: State) -> list[str]:
        impl = state.data.get("impl") or {}
        failing = sorted(t for t in REQUIRED if not impl.get(t))
        state.data["_last_failing"] = failing
        return [f"test_{t} FAILED" for t in failing]


def main() -> int:
    live = "--live" in sys.argv
    model = Model(live=live)
    print(f"\n=== self-correcting loop demo ({'LIVE Claude' if model.live else 'offline mock'}) ===\n",
          file=sys.stderr)
    engine = LoopEngine(DemoAdapter(model), max_iters=5, trace=Trace())
    result = engine.run(goal="Implement sum(nums) so all tests pass.")
    print("\n=== result ===", file=sys.stderr)
    print(f"success={result.success} iterations={result.iterations}", file=sys.stderr)
    print("\nThe wow moment: iteration 1 shipped a bug, verify caught it, iteration 2 fixed it.",
          file=sys.stderr)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
