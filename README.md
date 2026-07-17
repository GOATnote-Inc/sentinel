# SENTINEL

**An event-triggered, self-correcting ops agent.** A live event stream flows in; with zero
human intervention SENTINEL detects incidents, plans with Claude, acts through a policy-gated
tool registry, **verifies by re-inspecting the actual state that fired the event**, and
self-corrects when the first fix isn't enough. Everything it does streams to a glass-box UI
with a cited audit trail.

*Loop Engineering Hackathon (Jul 17, 2026) — track: Agentic Workflows.*

![SENTINEL glass box](docs/screenshot.png)

## Run it (one command)

```bash
./demo.sh              # live Claude plans if ANTHROPIC_API_KEY is available
./demo.sh --offline    # fully offline: deterministic cached plans (wifi-proof)
```

Open http://localhost:8787 — the feed auto-starts a few seconds later. There is no run
button; the loop is triggered by the stream. Measured on the build machine: detect →
verified fix in **~10s**; the full two-incident golden path in **~68s**, hands off.

## What you'll watch (≤90 seconds)

1. Routine heartbeats scroll — then a **DiskAlert** fires (94% on `checkout-api`).
2. PLAN (live Claude, short prompts) → ACT (`rotate_logs`) → **VERIFY re-inspects the disk:
   91%, still over threshold** → CORRECT → `purge_archived_logs` → verify passes at 66%.
   That failed-then-corrected beat is engineered to be deterministic (archives share the
   partition), so the self-correction is real mechanics, not luck.
3. A **DBAlert** on `billing-db` arrives. The agent plans a restart — the policy gate
   **BLOCKS** it (no restarts on prod-db class) and SENTINEL **escalates NEEDS HUMAN** with
   the full evidence trail. Autonomy with guardrails, and an honest failure mode.
4. Incidents queue **serially**; ad-hoc incidents can be injected any time (footer buttons
   or `POST /inject/<type>`) and are handled unscripted.

## What's real vs seeded (honesty ledger)

| Piece | Status |
|---|---|
| Loop engine (plan/act/observe/verify/correct), serial queue, retry-cap escalation | real |
| plan() = Claude (`claude-haiku-4-5`), 10s hard timeout → deterministic runbook fallback | real (flag: `SENTINEL_OFFLINE`) |
| verify() re-inspection, per-incident detect→fix timing in the audit log | real, measured |
| The "infrastructure" (6 services) + incident timeline (5s / 60s) | simulated world, seeded |
| Nexla feed / Zero.xyz tools / Pomerium gate | **local fallbacks** behind live↔local env flags (`SENTINEL_NEXLA/ZERO/POMERIUM`); UI labels tell the truth at all times |
| Akash | Dockerfile + SDL prepared (`akash-deploy.yaml`); not deployed |

## Architecture

```
feed (Nexla | local) ──> serial queue ──> loop_engine ──> tools (Zero.xyz | local)
                                            │   ▲                │
                                            │   └── policy gate (Pomerium | local)
                                            ▼
                              SSE glass box: feed · queue · loop steps · audit log
```

The engine (`loop_engine/`) is ~100 lines and domain-agnostic; SENTINEL is one adapter
(`skins/ops_skin.py`) plus a simulated world. Re-skinning it to another incident domain
(e.g. recruiting ops: failed interview-transcript deliveries → replay → verify) is a new
skin, not a rebuild.

## Rehearse / verify the claims

```bash
.venv/bin/python -m sentinel.rehearse            # stopwatch-graded golden path (online)
.venv/bin/python -m sentinel.rehearse --offline  # same, fully offline
```

Prints every beat with timestamps and PASSes only if: the seeded incident resolves in
exactly 2 iterations, the out-of-policy action is blocked then escalated, heartbeats keep
flowing after the story, and the whole path lands under 90s.
