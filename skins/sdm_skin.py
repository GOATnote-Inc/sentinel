"""SDM / consent / discharge skin — the verify oracle IS the medical-legal checklist.

Same loop engine as every other skin. The difference is that `verify()` encodes the
requirements documented (and cited) in hackathon/sdm-module/01-medical-legal-reference.md:

  * informed-consent 5 elements (capacity, disclosure, understanding, voluntariness, consent)
  * options MUST include the "no treatment" alternative (materiality; Cobbs/Canterbury)
  * every material risk carries severity AND probability (materiality = severity x probability)
  * patient values elicited (the SDM part; Elwyn/SHARE)
  * teach-back prompt + recorded confirmation of understanding (AHRQ)
  * patient-facing text at <= 6th-grade reading level (AHRQ; AMA/NIH)
  * every clinical claim grounded in the encounter (no unsupported statements)
  * CMS-mandated SDM elements when applicable (e.g., LDCT NCD 210.14)

A miss is a violation; the engine feeds violations back into the next draft and self-corrects.
The disclosure standard is CONFIGURABLE (state-specific law) and never hard-coded.

NOT legal/medical advice. Synthetic data only. See the module README.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from loop_engine.adapter import State
from loop_engine.model import Model

# CMS NCD 210.14 required counseling/SDM elements for lung-cancer LDCT screening.
MANDATED_ELEMENTS = {
    "ldct_lung_screening": [
        "benefits_and_harms", "false_positive_rate", "over_diagnosis",
        "radiation_exposure", "follow_up_testing", "adherence_to_annual_screening",
        "smoking_cessation_counseling", "decision_aid_used",
    ],
}

# ED per-complaint red-flag templates (reference §5.4). Each entry: phrases, at least a
# minimum number of which must appear in the patient-facing text, so "return if worse" alone
# can never pass. Clinical reviewers own this list — extend per deployment.
ED_RED_FLAGS = {
    "chest pain": {"min": 3, "phrases": [
        "chest pain comes back", "pain spreads to your arm", "pain spreads to your jaw",
        "short of breath", "sweating", "call 911"]},
    "abdominal pain": {"min": 3, "phrases": [
        "pain moves to your right lower belly", "pain gets much worse", "fever",
        "vomiting that won't stop", "blood in", "belly becomes hard", "call 911"]},
    "headache": {"min": 3, "phrases": [
        "worst headache of your life", "sudden", "stiff neck", "fever", "confusion",
        "weakness or numbness", "trouble speaking", "call 911"]},
    "head injury": {"min": 3, "phrases": [
        "repeated vomiting", "hard to wake", "confusion", "worsening headache",
        "weakness or numbness", "seizure", "blood thinner", "call 911"]},
    "back pain": {"min": 3, "phrases": [
        "trouble controlling your bladder", "trouble controlling your bowels",
        "numbness in your groin", "weakness in your legs", "fever", "return to the emergency"]},
    "fever": {"min": 2, "phrases": [
        "not drinking", "hard to wake", "rash", "trouble breathing", "seizure",
        "return to the emergency"]},
}

# A defensible AMA (against-medical-advice) record: informed REFUSAL, mirror of consent.
AMA_REQUIRED = {
    "capacity_assessed": "capacity not assessed for AMA departure",
    "risks_of_leaving_disclosed": "specific risks of leaving (incl. death where applicable) not disclosed",
    "alternatives_offered": "alternatives (incl. partial treatment) not offered",
    "may_return_anytime": "patient not told they may return at any time",
    "followup_still_provided": "discharge instructions/follow-up not still provided",
    "signature_or_refusal_documented": "signature (or documented refusal to sign) missing",
}

DRAFT_SYSTEM = (
    "You are a clinical shared-decision-making documentation agent. Produce a STRICT JSON object "
    "for the requested artifact. Structure options using the Elwyn three-talk / AHRQ SHARE model. "
    "Disclose material risks (each with severity and probability), benefits, and ALL alternatives "
    "INCLUDING the option of no treatment. Elicit the patient's values. Write `patient_text` at a "
    "5th-6th grade reading level (short words, short sentences). Every clinical claim in `claims` "
    "must cite verbatim evidence from the encounter/record; omit anything you cannot ground."
)

# JSON shape the model is asked to return (superset across artifact types).
SCHEMA_HINT = {
    "options": [{"name": "str", "benefits": ["str"],
                 "risks": [{"desc": "str", "severity": "low|moderate|high|grave",
                            "probability": "rare|uncommon|common"}],
                 "is_no_treatment": "bool"}],
    "patient_values": "str",
    "decision": "str",
    "capacity_assessed": "bool",
    "voluntary": "bool",
    "teach_back_prompt": "str",
    "understanding_confirmed": "bool",
    "patient_text": "str (<=6th grade)",
    "claims": [{"claim": "str", "evidence": "str (verbatim from encounter)"}],
    "mandated_elements": ["str"],
    "ama": {"capacity_assessed": "bool", "risks_of_leaving_disclosed": "bool",
            "alternatives_offered": "bool", "may_return_anytime": "bool",
            "followup_still_provided": "bool", "signature_or_refusal_documented": "bool"},
}


@dataclass
class SDMSkin:
    model: Model
    encounter: str                              # synthetic transcript
    record: dict | None = None                  # synthetic FHIR bundle
    output_type: str = "sdm"                    # "sdm" | "consent" | "discharge"
    disclosure_standard: str = "reasonable_patient"   # NEVER hard-code; state-specific
    mandated_sdm: str | None = None             # e.g. "ldct_lung_screening"
    reading_grade_max: float = 6.0
    care_setting: str = "ed"                    # "ed" (default) | "inpatient" | "clinic"
    chief_complaint: str | None = None          # keys ED_RED_FLAGS, e.g. "chest pain"
    disposition: str = "discharge"              # "discharge" | "ama"

    name: str = "sdm-consent-discharge"

    def plan(self, state: State) -> str:
        viol = state.data.get("_violations", [])
        if not state.data.get("artifact"):
            return (f"Draft the {self.output_type} artifact grounded in the encounter, "
                    f"disclosure standard = {self.disclosure_standard}.")
        return f"Revise to fix these compliance violations, changing nothing else: {viol}"

    def act(self, plan: str, state: State) -> State:
        viol = state.data.get("_violations", [])
        prompt = (
            f"ARTIFACT TYPE: {self.output_type}\n"
            f"DISCLOSURE STANDARD: {self.disclosure_standard}\n"
            + (f"CMS-MANDATED SDM: {self.mandated_sdm}; required elements: "
               f"{MANDATED_ELEMENTS.get(self.mandated_sdm, [])}\n" if self.mandated_sdm else "")
            + f"\nENCOUNTER (source of truth):\n{self.encounter}\n\n"
            + f"PATIENT RECORD (synthetic FHIR):\n{json.dumps(self.record)[:3000] if self.record else 'none'}\n\n"
            + (f"FIX THESE violations from the last draft: {viol}\n" if viol else "")
            + f"Return ONLY JSON in this shape:\n{json.dumps(SCHEMA_HINT)}"
        )
        raw = self.model.complete(system=DRAFT_SYSTEM, prompt=prompt, max_tokens=2500)
        state.data["artifact"] = _safe_json_obj(raw) or {}
        state.data["_show"] = _summarize(state.data["artifact"])
        return state

    def verify(self, state: State) -> list[str]:
        """The medical-legal checklist. Empty list == defensible & shippable."""
        a = state.data.get("artifact") or {}
        v: list[str] = []

        # --- informed-consent elements (reference §3.1, §4) ---
        if not a.get("capacity_assessed"):
            v.append("MISSING: decision-making capacity not assessed/recorded")
        if not a.get("voluntary", False):
            v.append("MISSING: voluntariness not confirmed")

        # --- options, alternatives, and materiality (reference §3.2) ---
        options = a.get("options") or []
        if len(options) < 2:
            v.append("MISSING: fewer than two options presented")
        if not any(o.get("is_no_treatment") for o in options):
            v.append("MISSING: the 'no treatment' alternative was not disclosed")
        for o in options:
            if o.get("is_no_treatment"):
                continue
            if not o.get("benefits"):
                v.append(f"MISSING: benefits for option '{o.get('name','?')}'")
            risks = o.get("risks") or []
            if not risks:
                v.append(f"MISSING: material risks for option '{o.get('name','?')}'")
            for r in risks:  # materiality = severity x probability -> both required
                if not r.get("severity") or not r.get("probability"):
                    v.append(f"INCOMPLETE RISK in '{o.get('name','?')}': "
                             f"needs both severity and probability ({r.get('desc','?')})")

        # --- SDM / values + decision (reference §1) ---
        if not (a.get("patient_values") or "").strip():
            v.append("MISSING: patient values/preferences not elicited (no SDM)")
        if not (a.get("decision") or "").strip():
            v.append("MISSING: the decision reached was not recorded")

        # --- teach-back / understanding (reference §2, §4) ---
        if not (a.get("teach_back_prompt") or "").strip():
            v.append("MISSING: no teach-back prompt generated")
        if not a.get("understanding_confirmed"):
            v.append("MISSING: patient understanding not confirmed via teach-back")

        # --- readability (reference §2) ---
        text = a.get("patient_text") or ""
        if text.strip():
            grade = flesch_kincaid_grade(text)
            a["_reading_grade"] = round(grade, 1)
            if grade > self.reading_grade_max:
                v.append(f"READABILITY: patient_text at grade {grade:.1f} > "
                         f"{self.reading_grade_max} (simplify wording)")
        else:
            v.append("MISSING: no patient-facing text")

        # --- grounding: every claim cited (reference §4) ---
        claims = a.get("claims") or []
        if not claims:
            v.append("MISSING: no grounded claims (nothing cited to the encounter)")
        for c in claims:
            if not self._is_supported(c.get("claim", ""), c.get("evidence", "")):
                v.append(f"UNSUPPORTED CLAIM: {c.get('claim','')[:70]}")

        # --- discharge-specific content (reference §5) ---
        if self.output_type == "discharge":
            v += self._discharge_gaps(a)
            if self.care_setting == "ed":
                v += self._ed_gaps(a)
            if self.disposition == "ama":
                v += self._ama_gaps(a)

        # --- CMS-mandated SDM elements (reference §3.3) ---
        if self.mandated_sdm:
            present = set(a.get("mandated_elements") or [])
            for req in MANDATED_ELEMENTS.get(self.mandated_sdm, []):
                if req not in present:
                    v.append(f"MANDATED ({self.mandated_sdm}): missing element '{req}'")

        state.data["_violations"] = v
        state.data["_show"] = _summarize(a)
        return v

    # --- helpers -------------------------------------------------------------
    def _discharge_gaps(self, a: dict) -> list[str]:
        text = (a.get("patient_text") or "").lower()
        gaps = []
        needles = {
            "return precautions / red-flag symptoms": ["call 911", "come back", "return", "emergency", "red flag"],
            "follow-up plan": ["follow up", "follow-up", "appointment", "see your"],
            "medications / reconciliation": ["medic", "take ", "dose", "stop taking"],
            "whom to call": ["call ", "phone", "number"],
        }
        for label, keys in needles.items():
            if not any(k in text for k in keys):
                gaps.append(f"DISCHARGE MISSING: {label}")
        return gaps

    def _ed_gaps(self, a: dict) -> list[str]:
        """ED discharge (reference §5.4): condition-specific red flags, time-specific
        follow-up, and honest diagnostic-uncertainty wording. Generic 'return if worse'
        can never satisfy this gate."""
        text = (a.get("patient_text") or "").lower()
        gaps: list[str] = []
        tmpl = ED_RED_FLAGS.get((self.chief_complaint or "").lower())
        if tmpl:
            hits = sum(1 for p in tmpl["phrases"] if p in text)
            if hits < tmpl["min"]:
                gaps.append(
                    f"ED RED FLAGS: only {hits}/{tmpl['min']} condition-specific return "
                    f"precautions for '{self.chief_complaint}' — generic wording is not enough. "
                    f"Use e.g.: {tmpl['phrases']}")
        elif self.chief_complaint:
            gaps.append(f"ED RED FLAGS: no template for '{self.chief_complaint}' — "
                        f"add condition-specific return precautions manually")
        # time-specific follow-up: "in N days", "within N days", "tomorrow"
        if not re.search(r"(within|in)\s+\d+\s+(day|week)|tomorrow", text):
            gaps.append("ED FOLLOW-UP: follow-up is not time-specific (who + within how many days)")
        # preserve diagnostic uncertainty — no false reassurance
        if not re.search(r"today|at this time|so far", text):
            gaps.append("ED UNCERTAINTY: instructions should say what we did not find *today*, "
                        "not imply the condition is ruled out forever")
        return gaps

    def _ama_gaps(self, a: dict) -> list[str]:
        """AMA departure = informed refusal; a signed form alone is not a defense (§5.4)."""
        ama = a.get("ama") or {}
        return [f"AMA MISSING: {msg}" for key, msg in AMA_REQUIRED.items() if not ama.get(key)]

    def _is_supported(self, claim: str, evidence: str) -> bool:
        if not claim:
            return True
        if not (evidence or "").strip():
            return False
        # Live: ask the model to audit; offline: require the evidence be present in the encounter.
        if self.model.live:
            raw = self.model.complete(
                system=("Strict clinical auditor. Return JSON {\"supported\": true|false}. "
                        "False unless the evidence clearly supports the claim and appears in the encounter."),
                prompt=f"CLAIM: {claim}\nEVIDENCE: {evidence}\nENCOUNTER:\n{self.encounter}",
                max_tokens=80,
            )
            return bool(_safe_json_obj(raw).get("supported", False))
        return evidence.strip().lower() in self.encounter.lower()


# --- readability: Flesch-Kincaid grade level, no external deps ---------------
def flesch_kincaid_grade(text: str) -> float:
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    words = re.findall(r"[A-Za-z]+", text)
    if not words:
        return 0.0
    syllables = sum(_syllables(w) for w in words)
    return 0.39 * (len(words) / sentences) + 11.8 * (syllables / len(words)) - 15.59


def _syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and n > 1:  # silent-e heuristic
        n -= 1
    return max(1, n)


def _summarize(a: dict) -> str:
    opts = a.get("options") or []
    return (f"opts={len(opts)} no_tx={'y' if any(o.get('is_no_treatment') for o in opts) else 'n'} "
            f"values={'y' if a.get('patient_values') else 'n'} "
            f"teachback={'y' if a.get('understanding_confirmed') else 'n'} "
            f"grade={a.get('_reading_grade','?')} claims={len(a.get('claims') or [])}")


def _safe_json_obj(raw: str) -> dict:
    i, j = raw.find("{"), raw.rfind("}")
    if i == -1 or j == -1 or j < i:
        return {}
    try:
        return json.loads(raw[i:j + 1])
    except json.JSONDecodeError:
        return {}
