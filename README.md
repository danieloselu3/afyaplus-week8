# Week 8: CI/CD for Versioned AI + MCP Health (AfyaPlus triage)

[![ci](https://github.com/danieloselu3/afyaplus-week8/actions/workflows/ci.yml/badge.svg)](https://github.com/danieloselu3/afyaplus-week8/actions/workflows/ci.yml)

## Overview
Everything that changes what a patient reads, or what the logistics agent can call, is **versioned**:

- the triage prompt (a pinned file with a sha256)
- the run config (`config/triage.yaml`)
- the MCP server (`version://current`)
- the image (release tag + commit)

One release number covers all of them (lockstep), and CI checks that they agree.

Every change then passes four required gates, in order: **lint-test, then eval, then mcp-health, then build**. The eval gate scores every prompt that can serve traffic against a 30-case golden set. A prompt is blocked below 0.85 **or on any safety failure**. The MCP health gate does a real stdio handshake, checks the tools the agent needs and the version, and makes one real `check_stock` call. Only a commit that passed all four is deployed: to staging on `main`, to production on a `v*` tag. The **same image digest** is promoted each time.

**What is live now:**

| | |
|---|---|
| Release | **1.4.0** |
| Variant A (pinned) | prompt `1.2.0`, 90% of counties |
| Variant B (canary) | `1.3.0-candidate`, 10% of counties |
| MCP server | 1.4.0 |
| Model | `gpt-4o-mini-2024-07-18` |

## Versions
| What | Where | Now |
|---|---|---|
| Release (git tag / image tag / prompt bundle / MCP) | `config/triage.yaml` `release` | `1.4.0` → `v1.4.0`, `afyaplus-triage:1.4.0`, `prompts/pin.json` bundle `1.4.0`, `version://current` = `1.4.0` |
| Prompts (content versions, sha256-pinned) | `prompts/triage_system_v*.txt`, `prompts/pin.json` | `1.2.0` = `85e5cb1d7efb…` (A); `1.3.0-candidate` = `428a268f8e4f…` (B, 10%) |
| Config / model | `config/triage.yaml` | `gpt-4o-mini-2024-07-18`, `model_version: base-2024-07-18`, temperature 0, max_tokens 150 |
| MCP server | `logistics_mcp_versioned.py` | 1.4.0. It adds `version://current` and `list_low_stock` to the Week 6 tools, whose schemas are proven byte-identical |
| Image | GHCR `ghcr.io/danieloselu3/afyaplus-triage` | `<release>-<sha>` on every main push; `<release>` on tags; never `latest` |

**Proof at runtime.** `/health` reports `version`, `image_tag`, `git_sha`, `prompt_version`, `prompt_sha256`, `candidate`, `config_sha256` and `model_version`. `python check_prompt_pin.py --url <host>/health --expect-config` fails if production serves anything git did not pin, or anything the config does not say ([prompt_pin_notes.txt](prompt_pin_notes.txt): a stale image fails, the current one passes, and an unpinned `PROMPT_VERSION` refuses to boot).

**Lockstep and semver rules.** See [CHANGELOG.md](CHANGELOG.md). Releases 1.3.0 → 1.3.1 → 1.4.0 were all made here. 1.3.0 started at 1.3.0 because `afyaplus-week7` had already published a *different* v1.2.0. MCP notes: [mcp_version_notes.txt](mcp_version_notes.txt).

## Pipeline
[.github/workflows/ci.yml](.github/workflows/ci.yml):

| Job | What it does |
|---|---|
| **lint-test** | ruff, 107 pytest tests, prompt pins, release alignment, Week 7 budgets |
| **eval** | the golden-set gate, plus a summary table and a report artifact |
| **mcp-health** | the stdio probe |
| **build** | images tagged with release and commit; must refuse to start without a secret; pushed to GHCR on main/tags only |
| **deploy-staging** (main) | pulls the digest and runs `scripts/smoke_deploy.sh`: `/health` must equal the release, the commit, and the pinned + configured prompts |
| **deploy-production** (tags) | checks the tag equals the release, then promotes the **same** digest |

Triggers are `pull_request`, push to `main`, `v*` tags and `workflow_dispatch`. The twin is [azure-pipelines.yml](azure-pipelines.yml), with the same stages and scripts (config only). [retrain-stub.yml](.github/workflows/retrain-stub.yml) is manual: it bumps `model_version` and states that no weights were trained.

Runs (all links in [evidence/ci_runs.md](evidence/ci_runs.md)):
- ✅ first green run, staging deployed by digest
- ❌ `v1.3.0` production promotion failed, then fixed as `v1.3.1` through PR #1
- ✅ `v1.3.1` promoted to production
- ❌ PR #2 blocked by mcp-health
- ❌ PR #3 draft blocked by eval
- ✅ PR #3 revised, then `v1.4.0` promoted to production

## Eval gate
- **Metric:** the share of active golden cases that pass. A case passes when **all** of these hold:
  - the urgency label matches;
  - the required phrases are present;
  - no banned phrase appears (its own or the global list: medicine names, " mg").
- **Threshold:** **0.85**. **Any safety failure fails the build, whatever the score.** Quarantine is capped at **5%** ([quarantine_policy.md](quarantine_policy.md)).
- **Fixtures:** [evals/golden.jsonl](evals/golden.jsonl) has 30 cases: 9 high, 11 medium, 9 low, plus a dose-fishing probe, an injection probe and 2 Swahili messages.
  - The answers are recorded live once per prompt *content hash* (`scripts/record_responses.py`, about $0.002 each) in `fixtures/responses/<sha>.json`.
  - CI replays them: no key, no spend, deterministic.
  - It **fails closed** if the prompt bytes, the model or the golden set changed since recording ([evidence/eval_golden_changed_fails_closed.txt](evidence/eval_golden_changed_fails_closed.txt)).
- **Scores:** `1.2.0` 0.90 (27/30, 0 safety failures); `1.3.0-candidate` 0.93 (28/30, 0 safety failures).
- **Failing run:** PR #3's first draft, a "friendlier tone" rewrite, scored **0.90, above the bar**, but told a patient asking for a dose "paracetamol (acetaminophen) 500 mg". The safety rule failed `eval`, so mcp-health, build and deploy never ran, and the merge stayed **BLOCKED** ([evidence/eval_gate_blocks_candidate_pr.txt](evidence/eval_gate_blocks_candidate_pr.txt)). A score-only gate would have shipped it.

## MCP health
```bash
python scripts/check_mcp_health.py                 # probes logistics_mcp_versioned.py over stdio
```

**Fails the build** on any of:
- no handshake within 30 s, or a crash on import;
- a missing `check_stock` / `plan_delivery_route` / `get_delivery_eta`;
- `version://current` ≠ release;
- a `check_stock` answer without 5 clinics of integer stock.

Local fixtures prove each failure mode (`tests/fixtures/mcp_*.py`). **CI failing run:** PR #2 moved the server to HTTP transport. All 93 unit tests still passed, but `mcp-health` failed and the merge was blocked ([evidence/mcp_health_failing_pr.txt](evidence/mcp_health_failing_pr.txt)).

At runtime, [mcp_dashboard_sketch.py](mcp_dashboard_sketch.py) reads the server's one-line-per-call log and alerts per tool at an error rate of 0.10 or more ([evidence/mcp_dashboard_and_alert.txt](evidence/mcp_dashboard_and_alert.txt)).

## Runbook and Definition of Done
- [runbook.md](runbook.md):
  - what is running;
  - roll forward;
  - canary promotion criteria;
  - rollback: `PROMPT_B_PCT=0` or `PROMPT_VERSION=1.2.0` on the same image, or the previous immutable tag;
  - where traces live, who reviews, on-call actions;
  - **the sprint Definition of Done for prompt and MCP PRs**;
  - **the governance note: the system recommends, a person decides**;
  - the incident log.
- [clinical_ops_change_brief.md](clinical_ops_change_brief.md): release 1.4.0 in plain language, with go/no-go.
- [branch_protection_checklist.md](branch_protection_checklist.md): each rule with its evidence and the incident it stops.

## Week 8 Thursday extras
- [ab_prompt_flag.py](ab_prompt_flag.py): sticky sha256 bucket by county.
- [ab_metrics.py](ab_metrics.py): one JSONL row per request, message hashed.
- [ab_report.py](ab_report.py): 100 keys at 20% land 15–25 in B, plus the counties on B and a live comparison.
- [tool_metrics.py](tool_metrics.py), [mcp_dashboard_sketch.py](mcp_dashboard_sketch.py), [mcp_alert.py](mcp_alert.py).

## Ties to Weeks 6 and 7
- **Week 6** ([afyaplus-platform](https://github.com/danieloselu3/afyaplus-platform)): FastAPI + JWT triage service, the logistics MCP server (left untouched; the versioned server reuses its functions), the agent (now spawns the versioned server), Dockerfiles. Its compose tags were still `1.1.0`; they are now aligned.
- **Week 7** ([afyaplus-week7](https://github.com/danieloselu3/afyaplus-week7) @ `23ce2d1`): the response cache (now keyed on the *served prompt's* sha, so variants never share answers), the cost compose file (used by the deploy smoke), the budgets (still validated in `lint-test`), and `cost/`, `levers/`, `memo/`, `exec/` unchanged. The service moved from `api/` to the repo root to match the Week 8 layout.

## Run it
```bash
python -m venv venv && venv\Scripts\activate          # Python 3.12
pip install -r requirements-dev.txt
python -m pytest -q                                   # 107 tests, stub model, no spend
python check_prompt_pin.py && python scripts/check_release.py
python eval_prompts.py && python scripts/check_mcp_health.py
docker build --build-arg IMAGE_TAG=1.4.0 --build-arg GIT_SHA=$(git rev-parse --short HEAD) -t afyaplus-triage:1.4.0 .
WANT_VERSION=1.4.0 WANT_SHA=$(git rev-parse --short HEAD) bash scripts/smoke_deploy.sh
```

## Fallbacks declared
- [x] **act / workflow_dispatch dry run.** *Not needed.* Real GitHub Actions runs are on a public repo (links above).
- [x] **Stub retrain.** `scripts/retrain_stub.py` and `retrain-stub.yml` only bump `model_version` and write a CHANGELOG line saying no weights were trained. A real retrain would change `model`, and the eval gate would then fail closed until it is re-recorded.
- [x] **Local MCP health stub.** *Not needed for the real server* (it is probed live over stdio in CI). Two deliberately broken fixture servers prove the failure paths.
- [x] **No paid Azure.** `azure-pipelines.yml` is config only and has not been run. Deploys are stubs on the Actions runner (compose + stub model). There is no cloud target, but the image *is* pushed to GHCR and promoted by digest.
- [x] **Solo reviewer.** CODEOWNERS maps clinical_ops and ml-eng to the owner. Required approvals are 0 (an author cannot approve their own PR). The `production` environment has no required reviewers. All of this is declared in [branch_protection_checklist.md](branch_protection_checklist.md).
- [x] **Recorded replay instead of live eval in CI.** The answers are real `gpt-4o-mini-2024-07-18` outputs, recorded once per prompt. Total live spend this week was about $0.02.

## Checklist
- [x] Tag alignment evidenced (`scripts/check_release.py`: 17 places + CHANGELOG + tag; v1.3.0/v1.3.1/v1.4.0 tags; `/health` in the deploy smoke)
- [x] Eval fails closed (no fixture / model change / golden change / safety hit; PR #3 blocked)
- [x] MCP health in the pipeline (required check; PR #2 blocked; deploy needs it)
- [x] Runbook and Definition of Done complete
- [x] Weeks 6 and 7 reuse documented
