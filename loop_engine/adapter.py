"""The Adapter protocol — the ONLY thing you write per hackathon.

An Adapter turns the domain-agnostic loop into a concrete agent:
  - plan(goal, history) -> a natural-language next action
  - act(plan, state)    -> mutate/return new state (edit code, draft a note, call a tool)
  - verify(state)       -> list of violations; an EMPTY list means "done / success"

The `verify` oracle is your moat. Give it a REAL signal:
  - Day 1 (dev):      run the tests -> violations = failing tests.
  - Day 2 (clinical): check claims -> violations = statements not supported by transcript/FHIR.
Same engine, different oracle. That is the reusable technique.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class State:
    """Whatever the loop is working on. Skins put their artifacts in `data`."""
    goal: str
    data: dict = field(default_factory=dict)
    history: list[str] = field(default_factory=list)   # human-readable step log for `plan`


@runtime_checkable
class Adapter(Protocol):
    name: str

    def plan(self, state: State) -> str:
        """Return the next action to take, in natural language."""
        ...

    def act(self, plan: str, state: State) -> State:
        """Perform the planned action; return the (possibly mutated) state."""
        ...

    def verify(self, state: State) -> list[str]:
        """Return a list of violations. Empty list == success (loop exits)."""
        ...
