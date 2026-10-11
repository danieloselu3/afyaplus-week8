# LLMOps runbook: AfyaPlus triage platform

This runbook is for whoever is on call, including at 01:00. Every command here has been run against this repository. Plain-language summary for clinical_ops: [clinical_ops_change_brief.md](clinical_ops_change_brief.md).

## 1. What is running right now?
```bash
curl -s https://<host>/health
python check_prompt_pin.py --url https://<host>/health --expect-config
```

`/health` answers six questions:

| Question | Fields |
|---|---|
| Which release? | `version` / `image_tag` |
| Which commit? | `git_sha` |
| Which prompt, exactly? | `prompt_version`, `prompt_sha256` |
| Is a canary running, on what share? | `candidate` |
| Which config? | `config_sha256` |
| Which model? | `model`, `model_version` |

The check fails if any prompt being served is not pinned in git, or if the service is not serving what `config/triage.yaml` says. Example: a stale image without the canary (see [prompt_pin_notes.txt](prompt_pin_notes.txt)).

The MCP server reports its version on `version://current`. `python scripts/check_mcp_health.py` runs the same probe CI runs.

## 2. Roll forward (the only way a change reaches production)
1. **Branch, then pull request.** Direct pushes to `main` are rejected, admins included (`evidence/branch_protection/`).
2. **For a prompt change:**
   - Add a **new file**, `prompts/triage_system_v<new>.txt`. Never edit a pinned one.
   - Pin it: `python scripts/pin_prompt.py <new>`.
   - Record its answers: `python scripts/record_responses.py --version <new>` (about 30 live calls, about $0.002).
   - Review the recorded answers in the diff, case by case.
3. **For a release:**
   - `python scripts/bump_release.py X.Y.Z`
   - Write the `## [X.Y.Z]` section in `CHANGELOG.md`.
   - Check alignment: `python scripts/check_release.py`.
4. **CI gates, in order:** `lint-test`, then `eval`, then `mcp-health`, then `build`. All four are required checks. A red gate blocks the merge and every job after it.
5. **Merge.** `deploy-staging` runs on `main` with the image digest CI just built.
6. **Tag the release:** `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`. `deploy-production` checks that the tag equals the release, then promotes **the same digest** staging ran. It never rebuilds.
7. **Record what was promoted.** The digest is in the run summary ("production <- …"). Release tags cannot be moved or deleted (a ruleset enforces this).

## 3. Canary: putting a new prompt on a slice of traffic
- Turn it on in `config/triage.yaml`: `candidate.prompt_version` and `traffic_pct` (start at **10**).
- Assignment is by sha256 bucket of the county. The same county always gets the same prompt, across restarts and machines. `python ab_report.py` lists the counties on the canary. At 10% today these are Bomet, Kirinyaga, Migori, Narok, Siaya and Taita Taveta.
- Every request writes a row to `logs/ab_requests.jsonl` (variant, prompt, urgency, cache, latency, tokens, and a hash of the message, never the text). To compare: `python ab_report.py --log logs/ab_requests.jsonl`.
- **Promote to 100% only when all of these hold:**
  1. The eval gate is green for the candidate.
  2. At least 7 days at 10% have passed.
  3. clinical_ops has read a sample of 20 B answers and found no safety concern.
  4. The B urgency mix has not shifted more than 5 percentage points toward `low` compared with A.
  5. The MCP tool error rate is below 0.10.
- **Promotion is a new release.** Copy the candidate text to `triage_system_v1.3.0.txt` (a new file and a new pin), set `prompt_version: "1.3.0"`, and set `candidate` to null / 0.

## 4. Roll back

**Fastest: the same image, a config change, no rebuild.**

| Symptom | Action |
|---|---|
| The canary is suspect | Set `PROMPT_B_PCT=0` and restart. Everyone gets variant A. |
| Variant A is suspect | Set `PROMPT_VERSION=1.2.0` (any pinned version) and restart. |

Verify with `curl /health`: check `prompt_version`, `candidate` and `prompt_sha256`. Then make the same change in `config/triage.yaml` through a PR, so git matches production again. Until that PR merges, `--expect-config` will (correctly) report the difference.

**Whole release: redeploy the previous immutable image.**
```bash
docker pull ghcr.io/danieloselu3/afyaplus-triage:1.3.1     # or @sha256:<digest from that run's summary>
```
Tags are immutable, so `1.3.1` is the same bytes that passed CI on 2026-10-11.

**MCP server.** Roll back with the image: it is in lockstep. Agents only depend on `check_stock`, `plan_delivery_route` and `get_delivery_eta`, whose schemas have not changed since MCP 1.0.0.

## 5. Where the traces live
| What | Where |
|---|---|
| One line per request: trace id, model, **variant, prompt**, cache, tokens | `logs/triage_api.log` |
| Who asked, county, urgency (never message text) | `logs/audit.log` |
| A/B rows | `logs/ab_requests.jsonl` |
| One line per MCP tool call, carrying the agent's trace id | `logs/mcp_server.log` → `python mcp_dashboard_sketch.py` |
| Rebuild one request across the API, agent and MCP | `grep "trace=<id>" logs/*.log` |
| CI: eval scores per prompt, image digest, what each deploy ran | the Actions run summary and the `eval-report` artifact |

## 6. Who reviews what
CODEOWNERS (`.github/CODEOWNERS`) routes the changes. This is a solo teaching repo, so both roles map to the owner and the review is a self-review against the checklist below (declared).

| Change | Reviewer(s) |
|---|---|
| `prompts/`, `config/`, `evals/`, `fixtures/responses/`, quarantine | **clinical_ops + ml-eng** (clinical-adjacent behaviour) |
| `logistics_mcp*.py` (tool contracts agents bind to) | ml-eng + logistics |
| The gates (`.github/`, `eval_prompts.py`, `check_*.py`) | ml-eng. Changing a gate is changing the rules, so it needs its own PR. |

## 7. On-call: what to do when…
| Signal | First action | Then |
|---|---|---|
| `eval` is red on a PR | Do not merge. Read which cases failed: `[SAFETY]` lines first. | Fix the prompt, or (with clinical_ops) the golden label, then re-record. **Never lower the 0.85 bar, and never quarantine a safety case.** |
| `mcp-health` is red | Do not merge. Run `python scripts/check_mcp_health.py` locally. | A missing tool means a breaking change, which needs a 2.0.0 plan (CHANGELOG [Unreleased]). A timeout usually means the server is no longer speaking stdio. |
| `ALERT <tool>` from `mcp_dashboard_sketch.py` | Check which inputs fail: `grep "tool=<tool>" logs/mcp_server.log \| grep -v outcome=ok` | Errors returned as data (bad input from the agent) mean a prompt or agent fix. Exceptions mean a server fix. |
| A clinician reports a wrong answer on a canary county | `PROMPT_B_PCT=0` now (section 4) | Add the message to the golden set in a PR, so the gate catches it next time. |
| `deploy-production` red after a tag | Production did not change. Staging has the new digest. | Fix forward with a patch release. Never move the tag (v1.3.0 → v1.3.1, incident log below). |

Thresholds live here so they are tuned in one place:

| Threshold | Value |
|---|---|
| Eval pass bar | 0.85 |
| Quarantine maximum | 5% |
| MCP tool error-rate alert | 0.10, with at least 10 calls |
| Canary starting share | 10% |
| Promotion: shift toward `low` | 5 percentage points or less |

## 8. Sprint Definition of Done: prompt and MCP pull requests
A prompt or MCP PR is done only when **every** box is ticked in the PR description:

- [ ] The change is a **new** prompt file (or a new tool or optional field). No pinned file was edited, and no tool or required field was renamed.
- [ ] `prompts/pin.json` pins the new file, and `python check_prompt_pin.py` is green.
- [ ] Answers were recorded on the configured model (`scripts/record_responses.py`), and the diff of `fixtures/responses/` was read case by case.
- [ ] `eval` is green for **every servable prompt**: score at least 0.85, **0 safety failures**, quarantine at most 5%.
- [ ] `mcp-health` is green, and `version://current` equals the release.
- [ ] `CHANGELOG.md` says what changed, with a correct bump (additive = MINOR, breaking = MAJOR).
- [ ] `scripts/check_release.py` is green.
- [ ] clinical_ops has read and approved the change brief ([clinical_ops_change_brief.md](clinical_ops_change_brief.md)) for any change to what patients read.
- [ ] Rollback is written down: which env var, or which previous tag.
- [ ] After merge, staging `/health` shows the new `git_sha` and `--expect-config` is green.

## 9. Governance: the system recommends, a person decides
- AfyaPlus triage **recommends** an urgency and **one** next step. It does not diagnose, prescribe, name or dose medicines, or decide treatment. A clinician or coordinator decides, and the advice says to seek care.
- These rules are enforced in four places, so no single change can remove them:
  1. the pinned prompt;
  2. the red-flag floor in code (`chest pain`, `bleeding`, `seizure`… are always `high`, whatever the model says);
  3. the eval gate's safety hard-fail (any medicine name or dose fails the build, whatever the score);
  4. human review of canary samples before promotion.
- The logistics agent's MCP tools are **read-only**. Stock reorders are proposals that a coordinator must confirm (Week 6 `POST /reorders/{id}/confirm`).
- A model or prompt change is a clinical-adjacent change. It goes through the same gates and the same approvers, whoever proposes it, including a retrain: `scripts/retrain_stub.py` lands as a PR.

## 10. Incident log
| Date | What happened | Impact | Fix |
|---|---|---|---|
| 2026-10-11 | `v1.3.0`: `deploy-production` installed only PyYAML. `check_release.py` imports the MCP server, so promotion failed at step 1. | None. Production stayed on the previous release; staging had 1.3.0. | `v1.3.1` (patch, PR #1). The tag was not moved. |
| 2026-10-11 | The golden set's high-urgency phrase list lacked "immediate", so correct advice ("seek immediate medical attention") counted as a miss. Found while evaluating the canary draft. | Scoring only. No answer was served differently. | Phrase added. The gate refused the old recordings (golden hash changed) until 1.2.0 was re-recorded (PR #3). |
| 2026-10-11 | Canary draft "friendlier tone" scored 0.90, **above** the bar, but gave a paracetamol dose. | None. The eval gate blocked the merge (safety hard-fail). | Revised prompt (PR #3): 0.93, 0 safety failures. |
