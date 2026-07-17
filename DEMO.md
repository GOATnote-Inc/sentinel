# SENTINEL — 3-Minute Demo Script

> STATUS: FROZEN EARLY (12:45 PM — freeze pulled forward from 2:00 PM; only demo-path
> bugfixes + credential-gated flag flips allowed now). Numbers are MEASURED from the
> 3 CONSECUTIVE clean stopwatch runs at 12:38–12:42 PM:
> golden path 67.3s / 67.3s / 67.5s · detect→verified-fix 9.7s / 10.2s / 9.8s (live model).
> Backup captured: docs/sentinel-golden-path.webm + screenshots (12:44 PM).
> INTEGRATION TRUTH RIGHT NOW: model = **live claude-haiku-4-5** · Nexla/Zero.xyz/Pomerium =
> **local fallback** (flags ready, no credentials yet) · runtime = **localhost** (Akash SDL
> prepared, NOT deployed). Every claim below matches that; [LIVE-UPGRADE] marks the sentence
> swap if a credential lands before freeze.

## Setup (before slot): terminal in `hackathon/starter-kit`, browser at `localhost:8787`,
## backup video open in the next tab. Command ready: `SENTINEL_ENV_FILE=<env> ./demo.sh`

| Clock | Beat | Say / do |
|---|---|---|
| 0:00–0:20 | Hook | "Every ops incident steals 30 focused minutes from an engineer — and the queue never sleeps. Sentinel resolves incidents before anyone is paged." |
| 0:20–0:30 | What | "An event-triggered, self-correcting ops agent: plan, act, observe, verify, correct — with hard policy guardrails. Watch the glass box." |
| 0:30 | **Start feed** | Run `./demo.sh`. **Step back — hands visibly off the keyboard for the rest of the demo.** "The live feed is starting — nobody touches this keyboard again." |
| ~0:41 | Detect | Feed pane goes red: DiskAlert 94%. "There — it detected one. Queued, working it. Planning… that's Claude reasoning about the incident live… acting: rotate logs." |
| ~0:45 | **WOW: self-correction** | Pre-announce: "Now watch it check its own work." VERIFY fails (91% > 90%). "Verify re-inspected the actual disk — the fix wasn't enough. It caught its own insufficient fix… correcting… purging archives…" |
| ~0:50 | Verified fix | SUCCESS + audit entry. "Verified fixed — disk at 66%, re-inspected, not assumed. Detect to verified fix: ~10 seconds, zero humans." |
| 0:55–1:35 | Breathe / narrate | Heartbeats keep scrolling. "It's not replaying a script — routine traffic keeps flowing. The audit log cites the triggering event, every action, and the re-inspection result." |
| ~1:36 | **WOW 2: guardrail** | Pre-announce: "Next one it should NOT be allowed to fix." DBAlert on billing-db → ⛔ BLOCKED. "It planned a restart of a production database — the policy gate blocked it. [LIVE-UPGRADE: 'Pomerium blocked it.'] Autonomy WITH guardrails." |
| ~1:45 | Honest escalation | NEEDS HUMAN badge. "When it can't safely fix something, it doesn't fail silently — it escalates to a human with the full evidence trail. That's our answer to 'what if it's wrong?'" |
| 1:50–2:10 | Q&A bait | "Any of these event types can be injected ad-hoc — pick one later and watch it handled unscripted." |
| 2:10–2:30 | **Tool roll-call (honest)** | "Architecture: the feed layer is built for **Nexla** as the data-delivery spine, tools execute behind a **Zero.xyz**-style registry, every call passes a **Pomerium**-pattern policy gate — today those run as local fallbacks with live/local flags, and the UI labels exactly what's real. The plans you watched were **live Claude** on short prompts. It's containerized with an **Akash** SDL ready. [LIVE-UPGRADE per credential: swap in 'X is live right now — the label says so.'] |
| 2:30–2:45 | **The number** | "Measured on this machine today, three consecutive runs: detect → verified fix in **under 10 seconds** (9.7–10.2s), the full two-incident golden path in **67 seconds**, hands off. Thirty stolen minutes → ten hands-off seconds." |
| 2:45–3:00 | Why big | "Every ops queue is a loop waiting for this: senses, hands, guardrails, audit. Same engine re-skins to any incident domain — that's the company." |

## Metaview Q&A answer (prepared, honest)
"Recruiting ops has the same shape: interview no-shows, transcript-sync failures, pipeline
stalls — each is an event with a runbook and a verifiable end-state. Our adapter is a skin:
the feed already carries a simulated `interview_pipeline` event type — transcript delivery
fails, the agent replays the webhook, verify re-inspects delivery status. Wiring it to
Metaview's real APIs is exactly the Nexla-source + tool-registry pattern you just watched —
that's the re-skin, not a rebuild."

## What's real vs seeded (say it if asked; never bluff)
- REAL: the loop, live Claude plan() calls, the policy gate on every tool call, verify()
  re-inspecting simulated-infra state, serial queue, escalation, timing, audit log.
- SEEDED: the incident timeline (5s / 60s) and the world model (simulated services) —
  engineered so fix #1 is insufficient (archives share the partition), making the
  self-correction deterministic, not luck.
- FALLBACK (as of now): Nexla/Zero/Pomerium local implementations behind live↔local flags;
  labels in the UI tell the truth at all times.

## T-minus-15 PREFLIGHT (run before the slot; any FAIL → flip flag to local + strike sentence)
1. `date` — confirm slot time; phone timer set to 3:00.
2. Port: `lsof -i :8787` → kill strays.
3. Model: `.venv/bin/python -c "from loop_engine.model import Model; print(Model().complete(system='ok',prompt='ok',max_tokens=5))"` with env sourced → any text = live OK; error → run `./demo.sh --offline`, MODEL chip must read "offline cache", strike "live Claude" from roll-call.
4. Per live integration (only if flipped live): Nexla poll returns an event · Zero tool call round-trips · Pomerium proxy answers → else `SENTINEL_<X>=local` and strike its sentence.
5. Akash: only claim if the browser bar shows the Akash URL serving the UI.
6. Backup video open in adjacent tab; `--offline` rehearsed once this hour.
7. Browser: full-screen, ~125% zoom, dark room check.
