"""Glass-box trace. Judges grade what they can see — so make the loop visible.

Right now this prints structured, color-coded steps to the terminal. At the hackathon, also
push each Event to a web UI (server-sent events / websocket) for the Design + Wildcard score.
Keep the terminal fallback for a reliable on-stage demo.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Callable

# Step -> label + emoji, so the loop reads at a glance on stage.
_STYLE = {
    "PLAN": ("🧭", "\033[36m"),      # cyan
    "ACT": ("⚙️", "\033[35m"),       # magenta
    "OBSERVE": ("👁", "\033[34m"),   # blue
    "VERIFY": ("🔎", "\033[33m"),    # yellow
    "CORRECT": ("↩️", "\033[31m"),   # red — the self-correction beat; make it pop
    "SUCCESS": ("✅", "\033[32m"),   # green
    "FAIL": ("🛑", "\033[31m"),
}
_RESET = "\033[0m"


@dataclass
class Event:
    step: str            # PLAN | ACT | OBSERVE | VERIFY | CORRECT | SUCCESS | FAIL
    iteration: int
    message: str
    data: dict = field(default_factory=dict)
    ts: float = 0.0


@dataclass
class Trace:
    """Collects events and emits them live. Pass a `sink` to fan out to a web UI."""
    events: list[Event] = field(default_factory=list)
    sink: Callable[[Event], None] | None = None
    color: bool = True
    _t0: float = field(default_factory=lambda: 0.0)

    def emit(self, step: str, iteration: int, message: str, **data) -> Event:
        if not self._t0:
            self._t0 = time.time()
        ev = Event(step=step, iteration=iteration, message=message,
                   data=data, ts=time.time() - self._t0)
        self.events.append(ev)
        self._print(ev)
        if self.sink:
            try:
                self.sink(ev)
            except Exception:
                pass  # never let a broken UI sink kill the loop mid-demo
        return ev

    def _print(self, ev: Event) -> None:
        emoji, col = _STYLE.get(ev.step, ("•", ""))
        c, r = (col, _RESET) if self.color else ("", "")
        header = f"{c}{emoji} [{ev.ts:5.1f}s] iter {ev.iteration} {ev.step:<8}{r}"
        print(f"{header} {ev.message}", file=sys.stderr, flush=True)
        for k, v in ev.data.items():
            print(f"        └─ {k}: {v}", file=sys.stderr, flush=True)
