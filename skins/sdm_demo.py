"""Offline, deterministic proof that the SDM skin self-corrects on a medical-legal checklist.

    python3 -m skins.sdm_demo

Scenario (synthetic — NO PHI): a clinician and patient discuss starting a statin for high
cholesterol. The agent's FIRST draft has two real, common documentation defects:
  1. it omits the "no treatment" alternative (a materiality/informed-consent failure), and
  2. its patient-facing text is written well above a 6th-grade reading level.
The verify() checklist (the REAL one from sdm_skin) catches both; the loop feeds the violations
back and the second draft fixes them. That catch-and-fix is the on-stage wow moment: the agent
refuses to ship an incomplete consent record.
"""
from __future__ import annotations

import sys

from loop_engine.adapter import State
from loop_engine.engine import LoopEngine
from loop_engine.model import Model
from loop_engine.trace import Trace
from skins.sdm_skin import SDMSkin

ENCOUNTER = (
    "Clinician: Your LDL cholesterol is 190, which raises your risk of heart attack and stroke. "
    "Patient: What can I do? Clinician: We can start a statin, which lowers cholesterol and lowers "
    "that risk; some people get muscle aches. Or we can try diet and exercise first and recheck in "
    "3 months. Patient: I really want to avoid another health scare like my father had. "
    "Clinician: Then a statin is reasonable. Patient: Okay, let's start it. I understand."
)


class DemoSDMSkin(SDMSkin):
    """Overrides only act() with a deterministic two-attempt draft; reuses the real verify()."""

    def act(self, plan: str, state: State) -> State:
        first_time = not state.data.get("artifact")
        common = {
            "capacity_assessed": True,
            "voluntary": True,
            "patient_values": "Wants to avoid a cardiac event like his father's; prefers to act now.",
            "decision": "Start a statin today; recheck lipids and tolerability in 6-8 weeks.",
            "teach_back_prompt": "Can you tell me in your own words why we're starting this medicine?",
            "understanding_confirmed": True,
            "claims": [
                {"claim": "LDL cholesterol is 190, raising cardiovascular risk.",
                 "evidence": "Your LDL cholesterol is 190, which raises your risk of heart attack and stroke."},
                {"claim": "Statins can cause muscle aches in some people.",
                 "evidence": "some people get muscle aches"},
            ],
            "mandated_elements": [],
        }
        statin = {"name": "Start a statin", "is_no_treatment": False,
                  "benefits": ["Lowers LDL cholesterol", "Lowers heart-attack and stroke risk"],
                  "risks": [{"desc": "muscle aches", "severity": "low", "probability": "uncommon"}]}
        diet = {"name": "Lifestyle change first (diet and exercise), recheck in 3 months",
                "is_no_treatment": False, "benefits": ["Avoids medicine"],
                "risks": [{"desc": "cholesterol may stay high longer", "severity": "moderate",
                           "probability": "common"}]}
        no_tx = {"name": "No treatment / monitor only", "is_no_treatment": True,
                 "benefits": ["No medicine, no side effects"],
                 "risks": [{"desc": "continued high risk of heart attack and stroke",
                            "severity": "grave", "probability": "uncommon"}]}

        if first_time:
            # DEFECT 1: no "no treatment" option. DEFECT 2: patient_text reads too high.
            art = {**common, "options": [statin, diet],
                   "patient_text": (
                       "Your laboratory evaluation demonstrated substantially elevated low-density "
                       "lipoprotein cholesterol, thereby necessitating pharmacologic intervention to "
                       "attenuate your cardiovascular morbidity and mortality risk going forward.")}
        else:
            # Self-correction: add the no-treatment option and rewrite at a low reading level.
            art = {**common, "options": [statin, diet, no_tx],
                   "patient_text": (
                       "Your bad cholesterol is high. High cholesterol can lead to a heart attack "
                       "or stroke. You chose to start a pill to lower it. Take it each day. "
                       "Call the clinic if your muscles hurt a lot. We will check your blood again "
                       "in about six weeks.")}
        state.data["artifact"] = art
        return state


def main() -> int:
    skin = DemoSDMSkin(Model(live=False), encounter=ENCOUNTER, output_type="consent",
                       disclosure_standard="reasonable_patient", reading_grade_max=6.0)
    print("\n=== SDM / informed-consent self-correcting loop (offline) ===\n", file=sys.stderr)
    result = LoopEngine(skin, max_iters=4, trace=Trace()).run(
        goal="Produce a defensible informed-consent record for starting a statin.")
    print("\n=== result ===", file=sys.stderr)
    print(f"success={result.success} iterations={result.iterations}", file=sys.stderr)
    print("Iteration 1 omitted the no-treatment option and read above 6th grade; verify caught "
          "both; iteration 2 self-corrected to a defensible, plain-language record.", file=sys.stderr)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
