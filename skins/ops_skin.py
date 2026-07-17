"""Ops skin — plan/act/verify for live ops incidents. The Day-1 SENTINEL adapter.

plan():  model-phrased choice from the incident's runbook ladder (Phase 2 wires Claude with
         a hard timeout; the deterministic ladder is always the fallback, so the demo can
         never hang on a model call).
act():   executes EXACTLY ONE tool through the policy-gated registry (Zero.xyz | local).
verify(): RE-INSPECTS the actual world state that fired the event — not model vibes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from loop_engine.adapter import State
from sentinel import config
from sentinel.registry import Registry, TOOL_DESCRIPTIONS, ToolResult
from sentinel.world import INCIDENTS, World

# One shared executor so a hung model call can never hang the loop: we wait
# MODEL_TIMEOUT_S for the future, then walk away and use the deterministic plan.
_EXEC = ThreadPoolExecutor(max_workers=2)


class OpsAdapter:
    name = "sentinel-ops"

    def __init__(self, incident_type: str, event: dict, world: World,
                 registry: Registry, model=None,
                 emit_meta: Callable[[str, dict], None] | None = None):
        self.itype = incident_type
        self.spec = INCIDENTS[incident_type]
        self.service = self.spec["service"]
        self.event = event
        self.world = world
        self.registry = registry
        self.model = model  # Phase 2: Claude plan phrasing w/ timeout fallback
        self.emit_meta = emit_meta or (lambda ch, d: None)

    # ---------------------------------------------------------------- plan --
    def plan(self, state: State) -> str:
        tried = state.data.get("tried", [])
        blocked = state.data.get("blocked_tools", [])
        candidates = [t for t in self.spec["ladder"] if t not in tried and t not in blocked]
        if not candidates:
            state.data["_next_tool"] = None
            reason = (f"policy denies every remaining remediation for {self.service}"
                      if blocked else "runbook exhausted with violations remaining")
            return f"No permitted remediation remains ({reason}) — escalate to a human."

        tool = candidates[0]
        state.data["_next_tool"] = tool
        fallback = self._deterministic_plan(tool, tried)
        return self._model_plan(tool, tried, fallback)

    def _deterministic_plan(self, tool: str, tried: list[str]) -> str:
        why = f"runbook step {len(tried) + 1} for {self.itype}"
        if tried:
            why = f"'{tried[-1]}' was insufficient — escalating to the next runbook step"
        return f"{tool} on {self.service}: {TOOL_DESCRIPTIONS[tool]} ({why})."

    def _model_plan(self, tool: str, tried: list[str], fallback: str) -> str:
        """Claude phrases the diagnosis + intent; the runbook keeps the ACTION
        deterministic. Hard timeout -> cached/deterministic plan, so venue wifi
        or a slow model can never stall the loop."""
        m = self.model
        if m is None or not getattr(m, "live", False):
            return fallback  # --offline / no key: deterministic plans, honestly labeled
        try:
            text = _EXEC.submit(self._call_model, tool, tried).result(
                timeout=config.MODEL_TIMEOUT_S)
            text = " ".join((text or "").split())
            if text:
                return f"{text} → executing {tool}"
        except Exception:
            pass
        return fallback + " (cached plan — model unavailable)"

    def _call_model(self, tool: str, tried: list[str]) -> str:
        live = self.world.get(self.service)
        hist = f" Previous attempt: {tried[-1]} was insufficient." if tried else ""
        return self.model.complete(
            system=("You are SENTINEL, an autonomous ops agent. Reply with ONE "
                    "sentence, max 28 words: your diagnosis and the remediation you "
                    "are executing now. No preamble."),
            prompt=(f"Incident: {self.event['summary']}. Live state: {live}.{hist} "
                    f"Runbook mandates next step: {tool} ({TOOL_DESCRIPTIONS[tool]})."),
            max_tokens=60,
        )

    # ----------------------------------------------------------------- act --
    def act(self, plan: str, state: State) -> State:
        tool = state.data.get("_next_tool")
        if tool is None:
            state.data["needs_human"] = True
            state.data["_abort"] = ("no permitted remediation — escalating to a human "
                                    f"(event {self.event['id']})")
            state.data["_show_action"] = "no action taken — escalating to a human"
            return state

        res: ToolResult = self.registry.call(tool, self.service)
        state.data.setdefault("tried", []).append(tool)
        state.data.setdefault("actions", []).append(res.__dict__)
        if res.blocked:
            state.data.setdefault("blocked_tools", []).append(tool)
        state.data["_show_action"] = f"{tool}({self.service}) via {res.via} -> {res.detail}"
        self.emit_meta("action", {"event_id": self.event["id"], "incident": self.itype,
                                  **res.__dict__})
        return state

    # -------------------------------------------------------------- verify --
    def verify(self, state: State) -> list[str]:
        # Re-inspect the SAME condition that fired the event, from live world state.
        return self.spec["check"](self.world, self.service)
