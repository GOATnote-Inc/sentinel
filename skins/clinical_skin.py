"""Day 2 skin — "Beyond the Note": agentic post-visit clinical workflow.

SAME engine as Day 1. The only real change is the verify oracle:
    Day 1: "do the tests pass?"      -> objective build signal
    Day 2: "is every claim supported by the transcript / FHIR record?" -> objective trust signal

That citation-grounded verify IS the healthcare trust moat and the live wow moment: the loop
catches a claim the conversation never supported, drops it, and self-corrects.

Inputs are SYNTHETIC — never use PHI. Transcripts: generate with Claude. Patient record: Synthea.

    from loop_engine.engine import LoopEngine
    from loop_engine.model import Model            # point at Claude for Healthcare on Day 2
    from skins.clinical_skin import ClinicalSkin
    engine = LoopEngine(ClinicalSkin(Model(live=True), transcript=TRANSCRIPT, fhir=FHIR_BUNDLE))
    engine.run(goal="Draft a grounded post-visit note + orders from this encounter.")
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from loop_engine.adapter import State
from loop_engine.model import Model

DRAFT_SYSTEM = (
    "You are a clinical documentation agent. From the visit transcript (and the patient's FHIR "
    "record), draft the requested artifact. Output STRICT JSON: a list of objects "
    '{"claim": <clinical statement>, "evidence": <verbatim quote from transcript or FHIR path>}. '
    "Every clinical claim MUST cite evidence. If you cannot ground a claim, omit it."
)

VERIFY_SYSTEM = (
    "You are a strict clinical auditor. For the given claim and the provided evidence sources "
    '(transcript + FHIR), answer STRICT JSON {"supported": true|false, "why": <short reason>}. '
    "Mark false if the evidence does not clearly support the claim. Do not give benefit of the doubt."
)


@dataclass
class ClinicalSkin:
    model: Model
    transcript: str
    fhir: dict | None = None      # a Synthea FHIR bundle (synthetic)
    artifact: str = "SOAP note + orders + suggested ICD-10 codes"

    name: str = "clinical-beyond-the-note"

    def plan(self, state: State) -> str:
        rejected = state.data.get("_rejected", [])
        if not state.data.get("claims"):
            return f"Draft the {self.artifact}; every claim must cite the transcript or FHIR."
        return (f"{len(rejected)} claim(s) were unsupported and removed: {rejected}. "
                f"Re-draft without them and fill any real gaps only with cited claims.")

    def act(self, plan: str, state: State) -> State:
        rejected = state.data.get("_rejected", [])
        prompt = (
            f"Artifact to produce: {self.artifact}\n\n"
            f"TRANSCRIPT:\n{self.transcript}\n\n"
            f"FHIR (synthetic):\n{json.dumps(self.fhir)[:4000] if self.fhir else 'none'}\n\n"
            + (f"Do NOT reintroduce these unsupported claims: {rejected}\n" if rejected else "")
            + "Return the JSON list of {claim, evidence}."
        )
        raw = self.model.complete(system=DRAFT_SYSTEM, prompt=prompt, max_tokens=2000)
        state.data["claims"] = _safe_json_list(raw)
        state.data["_show_claims"] = f"{len(state.data['claims'])} claims drafted"
        return state

    def verify(self, state: State) -> list[str]:
        """Return unsupported claims. Empty == every line is evidence-grounded (ship it)."""
        violations: list[str] = []
        rejected: list[str] = []
        for item in state.data.get("claims", []):
            claim = item.get("claim", "")
            evidence = item.get("evidence", "")
            if not self._is_supported(claim, evidence):
                violations.append(f"UNSUPPORTED: {claim[:80]}")
                rejected.append(claim[:80])
        # keep only supported claims for the approved artifact
        state.data["claims"] = [c for c in state.data.get("claims", [])
                                if f"UNSUPPORTED: {c.get('claim','')[:80]}" not in violations]
        state.data["_rejected"] = rejected
        state.data["_show_supported"] = f"{len(state.data['claims'])} supported / {len(rejected)} rejected"
        return violations

    def _is_supported(self, claim: str, evidence: str) -> bool:
        # INTEGRATE: strengthen with Claude for Healthcare FHIR skill + ICD-10/CMS connectors.
        raw = self.model.complete(
            system=VERIFY_SYSTEM,
            prompt=(f"CLAIM: {claim}\nCITED EVIDENCE: {evidence}\n\n"
                    f"TRANSCRIPT (source of truth):\n{self.transcript}\n"
                    f"FHIR:\n{json.dumps(self.fhir)[:2000] if self.fhir else 'none'}"),
            max_tokens=200,
        )
        obj = _safe_json_obj(raw)
        return bool(obj.get("supported", False))


# --- tolerant JSON helpers (models sometimes wrap JSON in prose/fences) ---
def _safe_json_list(raw: str) -> list[dict]:
    obj = _extract_json(raw, "[")
    return obj if isinstance(obj, list) else []


def _safe_json_obj(raw: str) -> dict:
    obj = _extract_json(raw, "{")
    return obj if isinstance(obj, dict) else {}


def _extract_json(raw: str, opener: str):
    closer = "]" if opener == "[" else "}"
    i, j = raw.find(opener), raw.rfind(closer)
    if i == -1 or j == -1 or j < i:
        return None
    try:
        return json.loads(raw[i:j + 1])
    except json.JSONDecodeError:
        return None
