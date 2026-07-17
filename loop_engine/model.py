"""Model client wrapper — the ONE place you swap models across the two days.

Day 1: Anthropic API or AWS Bedrock (claims the AWS bounty).
Day 2: Claude for Healthcare (same interface — just change model id / client + system prompt).

Runs offline with a deterministic mock when no ANTHROPIC_API_KEY is set (or live=False), so you
can trust the loop mechanics tonight before wiring a real key.
"""
from __future__ import annotations

import os
from typing import Callable

# Latest Claude model ids (see the claude-api skill for the authoritative list):
#   claude-opus-4-8 · claude-sonnet-5 · claude-haiku-4-5-20251001
DEFAULT_MODEL = "claude-sonnet-5"


class Model:
    """Minimal text-in/text-out interface. Extend with tools/skills at the event."""

    def __init__(self, live: bool | None = None, model: str = DEFAULT_MODEL,
                 mock: Callable[[str, str], str] | None = None):
        self.model = model
        self._mock = mock
        # Default to live only if a key exists; callers can force with live=True/False.
        self.live = (live if live is not None
                     else bool(os.environ.get("ANTHROPIC_API_KEY")))
        self._client = None
        if self.live:
            try:
                import anthropic  # imported lazily so offline/mock runs need no SDK
                self._client = anthropic.Anthropic()
            except Exception as e:  # noqa: BLE001
                print(f"[model] live requested but SDK/key unavailable ({e}); using mock.")
                self.live = False

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        if self.live and self._client is not None:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        # ---- offline deterministic mock ----
        if self._mock:
            return self._mock(system, prompt)
        return _generic_mock(system, prompt)


def _generic_mock(system: str, prompt: str) -> str:
    return "MOCK: no model wired. Pass a `mock` fn or set ANTHROPIC_API_KEY and use --live."
