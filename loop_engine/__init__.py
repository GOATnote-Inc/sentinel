"""A tiny, reusable self-correcting agent loop: plan -> act -> observe -> verify -> correct.

Fork this on both hackathon days. Write only an Adapter (a "skin"); the loop is fixed.
"""
from .engine import LoopEngine, LoopResult
from .adapter import Adapter, State
from .trace import Trace, Event

__all__ = ["LoopEngine", "LoopResult", "Adapter", "State", "Trace", "Event"]
