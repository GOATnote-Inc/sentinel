# SENTINEL — 3-Minute Demo Script

> STATUS: FROZEN EARLY (12:45 PM — freeze pulled forward from 2:00 PM; only demo-path
> bugfixes + credential-gated flag flips allowed now). Numbers are MEASURED from the
> 3 CONSECUTIVE clean stopwatch runs at 12:38–12:42 PM:
> golden path 67.3s / 67.3s / 67.5s · detect→verified-fix 9.7s / 10.2s / 9.8s (live model).
> Backup captured: docs/sentinel-golden-path.webm + screenshots (12:44 PM).
> INTEGRATION TRUTH RIGHT NOW (updated 2:30 PM — THREE SPONSORS LIVE):
> · **Pomerium LIVE** — self-hosted proxy (docker), PPL route policy makes the deny in the
>   demo path: the prod-db restart is a real 403 from Pomerium, not our if-statement.
>   Full golden path PASS at 67.5s with the proxy deciding.
> · **Nexla LIVE** — CONCORD's evidence corpus flows through a governed Nexla webhook
>   connector → NexSet #435636 → pulled at boot ("evidence via Nexla NexSet #435636 (live,
>   governed)" on-screen). 13/13 gate checks PASS on governed evidence.
> · **Akash LIVE** — SENTINEL agent+UI serving at
>   http://o9ghl02midejp3jnq08rutruoc.ingress.cpu.aesservices.net (DSEQ 1784321934915).
> · model = live claude-haiku-4-5 (localhost demo) · Zero.xyz = local fallback (no creds —
>   say so if asked) · Metaview = interview_pipeline event type + prepared Q&A.
> Stage setup: TAB 1 localhost SENTINEL · TAB 2 Akash URL · TAB 3 CONCORD (make demo-gov,
> advanced to the blocked-claim beat).

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
| 1:50–2:20 | **ACT 2: the stakes** | _[switch to TAB 3 — CONCORD]_ "Now raise the stakes. Hospitals hand out discharge instructions, but there's no real surface for shared decision-making — least of all the against-medical-advice conversation. Agents can automate this — and **agentic automation in healthcare kills people when it's wrong**. Same gates, hardest domain: this is CONCORD. Eleanor, 90, food impaction, wants to leave. Watch — the model just called waiting 'perfectly safe': the grounding gate **blocked it**, redline on the clinician side, **nothing** reaches the patient. _[press B]_ Bound to real evidence — ASGE guideline, cited both sides. The evidence it's allowed to cite arrives through **Nexla** — governed, credentialed — it's on screen. Artifacts stay locked until teach-back passes and a human attests capacity." |
| 2:20–2:40 | **Tool roll-call (all true)** | "Three of your sponsors are load-bearing and live: **Pomerium**'s policy engine made that deny — a real 403 from a real proxy, the agent physically can't restart a prod database. **Nexla** delivers the only evidence the healthcare gate will trust. **Akash** — _[TAB 2, URL in the bar]_ — is running the agent and UI right now, deployed this afternoon. Plans were **live Claude**. Tool registry is Zero.xyz-shaped but ran local today — the labels never lie." |
| 2:40–2:50 | **The number** | "Measured, three consecutive runs: detect → verified fix **under 10 seconds**, full golden path **67 seconds**, hands off." |
| 2:50–3:00 | Close | "Thirty stolen minutes → ten hands-off seconds — and the same gates that fix your disk tonight are the ones that keep an autonomous agent from hurting Eleanor. Autonomy you can hand the most dangerous queue in the building. That's the company." |

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
- LIVE (as of 2:30 PM): Pomerium (self-hosted proxy, PPL deny in the demo path) · Nexla
  (governed NexSet #435636 feeding CONCORD's grounding gate) · Akash (SENTINEL deployment).
- FALLBACK: Zero.xyz-shaped local tool registry (no credentials today — say so plainly).
  Labels in both UIs tell the truth at all times; every integration flips live↔local by flag.

## T-minus-15 PREFLIGHT (run before the slot; any FAIL → flip flag to local + strike sentence)
1. `date` — confirm slot time; phone timer set to 3:00.
2. Port: `lsof -i :8787` → kill strays.
3. Model: `.venv/bin/python -c "from loop_engine.model import Model; print(Model().complete(system='ok',prompt='ok',max_tokens=5))"` with env sourced → any text = live OK; error → run `./demo.sh --offline`, MODEL chip must read "offline cache", strike "live Claude" from roll-call.
4. Pomerium: `docker ps | grep pomerium` + `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8443/toolexec/restart_service/billing-db` → **403** = live; else `SENTINEL_POMERIUM=local` + strike.
   Nexla: `curl -s -H "Authorization: Bearer $NEXLA_SESSION_TOKEN" -H "Accept: application/vnd.nexla.api.v1+json" "$NEXLA_API_URL/data_sets/435636/samples?output_only=1&count=1"` → JSON = live; else CONCORD runs `make demo-forced` + strike. (Token in starter-kit/.env; if 401, re-copy from Nexla UI → Get Session Token.)
5. Akash: `curl -sf http://o9ghl02midejp3jnq08rutruoc.ingress.cpu.aesservices.net/healthz`
   → JSON = claim stands, keep the tab open; dead → STRIKE the Akash sentence, close the tab.
   (Trial lease ~3 days; ttl.sh image expires ~1:33 PM tomorrow — outlives the demo.)
6. Backup video open in adjacent tab; `--offline` rehearsed once this hour.
7. Browser: full-screen, ~125% zoom, dark room check.
