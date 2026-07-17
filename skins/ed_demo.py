"""ED discharge self-correction demo (offline, deterministic — NO PHI, synthetic encounter).

    python3 -m skins.ed_demo

Scenario: low-risk chest pain worked up in the ED (normal ECG and troponins), discharged.
The agent's FIRST draft is the classic inadequate instruction — generic "come back if you feel
worse" — plus no time-specific follow-up and false-reassurance wording. The ED gate in
SDMSkin.verify() rejects all three; the loop self-corrects to condition-specific chest-pain
red flags, "we did not find a heart attack TODAY" wording, and 2-day follow-up.

That beat — the agent refusing to ship the exact instruction that loses lawsuits — is the demo.
"""
from __future__ import annotations

import sys

from loop_engine.adapter import State
from loop_engine.engine import LoopEngine
from loop_engine.model import Model
from loop_engine.trace import Trace
from skins.sdm_skin import SDMSkin

ENCOUNTER = (
    "Clinician: Your ECG and two troponin blood tests are normal, so we did not find a heart "
    "attack today. Your pain may be from the chest wall. Patient: So I'm okay to go home? "
    "Clinician: Yes, but chest pain can change, so I want you to see your doctor in two days, "
    "and come back immediately for certain warning signs. Patient: Okay, that makes sense."
)


class DemoEDSkin(SDMSkin):
    """Deterministic act(); reuses the REAL verify() including the ED gate."""

    def act(self, plan: str, state: State) -> State:
        first_time = not state.data.get("artifact")
        base = {
            "options": [
                {"name": "Discharge home with follow-up", "is_no_treatment": False,
                 "benefits": ["Sleep at home", "Follow-up with your own doctor"],
                 "risks": [{"desc": "a serious cause could still show up later",
                            "severity": "grave", "probability": "rare"}]},
                {"name": "Stay for observation", "is_no_treatment": False,
                 "benefits": ["More monitoring"],
                 "risks": [{"desc": "long stay, extra cost", "severity": "low",
                            "probability": "common"}]},
                {"name": "No follow-up / monitor only", "is_no_treatment": True,
                 "benefits": ["Nothing to schedule"],
                 "risks": [{"desc": "a missed heart problem could get worse",
                            "severity": "grave", "probability": "rare"}]},
            ],
            "patient_values": "Wants to go home; agrees to close follow-up.",
            "decision": "Discharge home with 2-day follow-up and strict return precautions.",
            "capacity_assessed": True, "voluntary": True,
            "teach_back_prompt": "Tell me in your own words which warning signs mean you call 911.",
            "understanding_confirmed": True,
            "claims": [
                {"claim": "ECG and two troponin tests were normal.",
                 "evidence": "Your ECG and two troponin blood tests are normal"},
                {"claim": "No heart attack was found today.",
                 "evidence": "we did not find a heart attack today"},
            ],
            "mandated_elements": [],
        }
        if first_time:
            # The classic inadequate ED instruction: generic, timeless, falsely reassuring.
            base["patient_text"] = (
                "Good news: your heart tests were fine. Take it easy and come back "
                "if you feel worse. Take your medicines and rest. Call us with questions.")
        else:
            base["patient_text"] = (
                "We did not find a heart attack today. Your tests were normal, but chest pain "
                "can change. See your doctor within 2 days. Call 911 right away if your chest "
                "pain comes back, if pain spreads to your arm or jaw, if you are short of "
                "breath, or if you start sweating with the pain. Come back to us any time you "
                "are worried. Take your medicines as before. Call the ER with questions.")
        state.data["artifact"] = base
        return state


def main() -> int:
    skin = DemoEDSkin(Model(live=False), encounter=ENCOUNTER, output_type="discharge",
                      care_setting="ed", chief_complaint="chest pain",
                      disclosure_standard="reasonable_patient", reading_grade_max=6.0)
    print("\n=== ED discharge self-correcting loop (offline) ===\n", file=sys.stderr)
    result = LoopEngine(skin, max_iters=4, trace=Trace()).run(
        goal="Produce defensible ED discharge instructions for low-risk chest pain.")
    print("\n=== result ===", file=sys.stderr)
    print(f"success={result.success} iterations={result.iterations}", file=sys.stderr)
    print("Draft 1 was the classic 'come back if worse' instruction; the ED gate rejected it "
          "(no condition-specific red flags, no time-specific follow-up, false reassurance); "
          "draft 2 self-corrected.", file=sys.stderr)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
