"""Day 1 skin — self-healing build/CI loop ("Green Again").

Verify oracle = the test suite (or Buildkite status): objective ground truth.
    plan  -> ask Claude for a fix given the current failures
    act   -> apply the fix to the repo
    verify-> run the tests; failing tests == violations

This is a working template. The two integration points to finish at the event are marked
INTEGRATE. Keep the loop; wire the tools. Fork loop_engine untouched.

Usage sketch:
    from loop_engine.engine import LoopEngine
    from loop_engine.model import Model
    from skins.dev_skin import DevSkin
    engine = LoopEngine(DevSkin(Model(live=True), repo="/path/to/seeded-repo",
                                test_cmd="pytest -q"))
    engine.run(goal="Make the test suite pass.")
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from loop_engine.adapter import State
from loop_engine.model import Model

SYSTEM = (
    "You are a senior engineer fixing a failing build. You are given the failing test output "
    "and relevant file contents. Respond with the COMPLETE corrected contents of the single "
    "file most likely at fault, and nothing else. Do not explain."
)


@dataclass
class DevSkin:
    model: Model
    repo: str
    test_cmd: str = "pytest -q"
    target_file: str | None = None  # the file the agent is allowed to edit (keep scope tiny for the demo)

    name: str = "dev-self-heal"

    def plan(self, state: State) -> str:
        failing = state.data.get("_last_output", "")
        if not failing:
            return "Run the tests to see what's failing, then fix the root cause."
        return f"Fix the failure. Test output tail:\n{failing[-800:]}"

    def act(self, plan: str, state: State) -> State:
        # First iteration may just be "observe" — only patch once we have failures + a target.
        if not state.data.get("_last_output") or not self.target_file:
            return state
        current = _read(self.target_file)
        fix = self.model.complete(
            system=SYSTEM,
            prompt=f"Failing tests:\n{state.data['_last_output'][-1500:]}\n\n"
                   f"File `{self.target_file}`:\n```\n{current}\n```\n\n"
                   f"Return the full corrected file contents only.",
            max_tokens=2000,
        )
        fix = _strip_fences(fix)
        if fix.strip():
            # INTEGRATE: for multi-file fixes, parse a diff instead. Single-file keeps the demo reliable.
            _write(self.target_file, fix)
            state.data["_show_patched"] = self.target_file
        return state

    def verify(self, state: State) -> list[str]:
        # INTEGRATE (sponsor bounty): swap this local run for the Buildkite REST API status
        # to make it a real CI loop.
        proc = subprocess.run(self.test_cmd, cwd=self.repo, shell=True,
                              capture_output=True, text=True)
        state.data["_last_output"] = proc.stdout + proc.stderr
        if proc.returncode == 0:
            return []
        return _failing_tests(state.data["_last_output"]) or ["tests failing (see output)"]


# --- small helpers (keep these boring and reliable) ---
def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def _write(path: str, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.rstrip().endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s


def _failing_tests(output: str) -> list[str]:
    # Cheap pytest failure extractor; tune to your runner at the event.
    return [ln.strip() for ln in output.splitlines()
            if ln.strip().startswith(("FAILED", "ERROR")) and "::" in ln][:10]
