# Week 7: Cost-Optimised AI Deployment (AfyaPlus triage)

[![ci](https://github.com/danieloselu3/afyaplus-week7/actions/workflows/ci.yml/badge.svg)](https://github.com/danieloselu3/afyaplus-week7/actions/workflows/ci.yml)

## Overview
This is the AfyaPlus triage API from Week 6: FastAPI with JWT, gpt-4o-mini behind it, in Docker. Week 7 adds visible cost controls and two measured optimisation levers.

**Workload.** 2,000 triage requests a day (60,000 a month). The stated spike is 10× that, an outbreak month of 20,000 a day.

**Unit cost.** **$3.11 per 1,000 requests all-in** today ($0.0031 a request), falling to **$0.42 per 1,000** in the spike month. The model itself is about 1% of that: $0.0371 per 1,000 before the levers and $0.0139 after. Most of the cost is people and the always-on container.

**Recommendation.** Go, on five conditions (see the one-pager).

Every figure is printed by a script in this repo, from live gpt-4o-mini runs on 2026-10-11 (about $0.01 in total) or from published prices.

## Cost model
- [cost/cost_model.md](cost/cost_model.md): the write-up, with every rate footnoted to a source, a measurement [M] or an assumption [A].
- Sources: [cost/cost_model.py](cost/cost_model.py) produces the table, and [cost/sensitivity.py](cost/sensitivity.py) shows what moves the bill. [cost/retry_storm.py](cost/retry_storm.py) covers the incident line.
- Token shape measured on 100 live calls: 122.7 prompt + 31.2 completion tokens ([fixtures/usage_recorded.json](fixtures/usage_recorded.json)). That is about a quarter of the course's teaching shape.

| | Monthly | $ / 1,000 all-in | $ / 1,000 tokens only |
|---|---:|---:|---:|
| Baseline, no levers | $186.65 | $3.11 | $0.0371 |
| Baseline, cache + batch (recommended) | $185.26 | $3.09 | $0.0139 |
| 10× spike, no levers | $249.75 | $0.42 | $0.0371 |
| 10× spike, cache per replica + batch (recommended) | $240.83 | $0.40 | $0.0223 |

## Deploy and budgets
```bash
cp api/.env.example api/.env          # then fill in OPENAI_API_KEY and JWT_SECRET
docker compose -f deploy/docker-compose.cost.yml up -d --build      # triage-api:1.2.0 + Redis
curl -s localhost:8000/health        # reports version, model, endpoint host and cache backend
```
- [deploy/docker-compose.cost.yml](deploy/docker-compose.cost.yml) sets the ceilings: 0.5 vCPU and 1 GiB per replica, Redis capped at 64 MB, a health check, and a pinned image tag. It also carries the **FinOps labels**: `service`, `version`, `env`, `cost-center`, `owner`. The `two-replicas` profile adds a second copy on :8002 for the shared-cache drill.
- **Budget alerts.** [azure_budget_triage.json](deploy/azure_budget_triage.json) and [aws_budget.json](deploy/aws_budget.json) + [aws_budget_notify.json](deploy/aws_budget_notify.json) set **$80 a month** on tag `service=triage-api`. Alerts fire at **80% actual** and **100% forecast**. [deploy/budget_alert_notes.md](deploy/budget_alert_notes.md) explains why $80 (the planned spike month's cloud spend, $77.47, rounded up), who is told, and the one pre-agreed action. [deploy/validate_budgets.py](deploy/validate_budgets.py) fails if the cap, threshold or tag drift from each other, from the compose labels or from the cost model.
- Replica ceiling: min 1, max 3, in [serverless-ish.yaml](deploy/serverless-ish.yaml) and [hpa.yaml](deploy/hpa.yaml). The tag-to-cloud mapping is in [ceiling_tags_checklist.md](deploy/ceiling_tags_checklist.md), and the endpoint switch drill in [endpoint_switch_notes.md](deploy/endpoint_switch_notes.md).
- Evidence: [deploy_compose_run.txt](evidence/deploy_compose_run.txt) has compose ps, `/health`, labels via `docker inspect`, and live limits. It also shows a MISS on replica 1 then a HIT on replica 2. More in [budget_validation.txt](evidence/budget_validation.txt), [endpoint_switch_drill.txt](evidence/endpoint_switch_drill.txt) and [load_test_one_replica.txt](evidence/load_test_one_replica.txt).

## Levers implemented
Full write-up with quality notes: [levers/measurements.md](levers/measurements.md). All runs are on fixed, seeded fixtures in [fixtures/](fixtures/).

1. **Response cache** ([api/response_cache.py](api/response_cache.py), wired into `/triage` with an `X-Cache` header). Same 100 calls, live:
   - hit rate **0 → 0.60** (gate ≥ 0.55)
   - **$ per 1k tokens $0.0371 → $0.0147**
   - p50 975 ms → 0 ms
   - p95 1,476 → 1,178 ms. The p95 is still a miss, and we say so.

   Through two running replicas sharing Redis: 100/100 OK, 60 HITs, HIT p95 10.6 ms vs MISS p50 1,005 ms. [cache before/after](evidence/lever1_cache_before_after.txt) · [HTTP, two replicas](evidence/lever1_http_replay_two_replicas.txt)
2. **Batch queue for after-hours messages** ([levers/batch_worker.py](levers/batch_worker.py): SQLite, retries, dead-letter, reads the live cache but never writes it). Same 24 messages:
   - **batch of 4: −31.6% cost, 96% agreement** with one-call answers
   - batch 8: −42.8%, 92%
   - batch 12: −46.8%, 88%

   [transcript](evidence/lever2_batch_before_after.txt)

**Quality notes.** The exact-match cache cannot make an answer worse. It does freeze one answer for 10 minutes (the model agreed with itself 98% of the time on repeats). Bigger batches *do* change answers, mostly downgrading `medium` to `low`, so the batch size is 4 and the red-flag safety floor still applies per message. No semantic cache: "chest pain" must never be answered as "chest tightness".

## API vs self-host memo
[memo/api_vs_selfhost.md](memo/api_vs_selfhost.md) (from [cost/breakeven.py](cost/breakeven.py)):
- **Stay on the API.** Self-hosting costs $834 to $3,861 a month fixed, against a model bill of about $2.
- Break-even is **26 M to 120 M requests a month, 433× to 2,003× today**. Even at gpt-4o prices it is still 23× to 105× today.
- Decision changers: sustained volume beyond about 26 M a month, a price rise *and* growth, or a data-residency ruling. For residency the first answer is a hosted in-region endpoint (the same `LLM_BASE_URL` switch), not owned GPUs.

## Executive one-pager
[exec/one_pager.pdf](exec/one_pager.pdf), built by [exec/build_one_pager.py](exec/build_one_pager.py) straight from the JSON outputs, so its figures cannot drift. **GO**, on these conditions:
1. Apply the $80 budget when the cloud account opens.
2. The key owner sets a $25 OpenAI monthly limit.
3. p95 stays under 2.5 s.
4. Re-measure the real repeat rate and batch agreement in month one.
5. When the model is down, the app returns an honest 503 and never invents advice.

## Ties to Week 6
`api/` is [afyaplus-platform](https://github.com/danieloselu3/afyaplus-platform)@`1b3c05f`, imported unchanged in the first commit. Week 7 changes:
- `response_cache.py`, wired into `/triage`
- `/health` also reports model, endpoint host and cache backend
- the `LLM_BASE_URL`/`LLM_MODEL` switch
- a configurable `TRIAGE_RATE_LIMIT_PER_MIN`
- `STUB_LATENCY_MS` for free load tests
- VERSION 1.2.0, with FinOps labels in the image

JWT, roles, the red-flag floor and the 503 behaviour are untouched. The 50 Week 6 tests still pass inside the 71; one, the `/health` test, was updated for the three new fields.

## Run it
```bash
python -m venv venv && venv\Scripts\activate          # Python 3.12
pip install -r requirements-dev.txt
python -m pytest -q                                   # 71 tests, stub model, no spend
python fixtures/make_fixtures.py                      # the fixed fixtures (seed 7)
python levers/cache_hitrate.py --mode off|on [--backend stub]
python levers/batch_measure.py [--backend stub]
python cost/cost_model.py && python cost/sensitivity.py && python cost/breakeven.py
python deploy/validate_budgets.py
python exec/build_one_pager.py
```

## Fallbacks declared
- [x] **Redis / dict cache.** Redis *was* used, in Docker, shared by two replicas and evidenced over HTTP. The in-process dict is also implemented, is the automatic fallback, and is the **recommended production default** until about 2.6 M requests a month (`cost/cost_model.md`).
- [x] **GPU quantization / mocked smoke.** Not attempted. The two levers are cache and batch, so no quantization or quality-proxy claim is made. Self-host figures in the memo are labelled estimates. The only GPU price we actually paid is Week 4's vast.ai RTX 4090.
- [x] **Paid cloud / config-only budgets.** No paid Azure or AWS account. The budgets are submitted as config and checked by `validate_budgets.py`, not applied to a subscription. Prices come from the public Azure Retail Prices API.
- [x] **No Kubernetes cluster.** `hpa.yaml` is config. The load evidence comes from Docker Compose: one replica on the free stub with 1 s of simulated model time.
- [x] **Rate limit raised for measurement runs only.** 120 a minute for the HTTP replay and 100,000 for the stub load test. The deploy default is 30 (Week 6's was 5).
- [x] **OpenAI project budget.** Recommended at $25 a month, but not configured by us; it needs the key owner.

## Checklist
- [x] $/1k at baseline and spike
- [x] Budget alert evidence (config + validator; not applied live, see fallbacks)
- [x] Two levers with measurements
- [x] Honest heuristic/quality notes
- [ ] Executive language reviewed by a non-author classmate: **pending**, to be done before submission

## Repository layout
```
api/        Week 6 service + response cache (lever 1)    cost/     Deliverable 1 + break-even
deploy/     Deliverable 2: compose, budgets, scaling       levers/   Deliverable 3: harnesses, results/, measurements.md
memo/       Deliverable 4                                  exec/     Deliverable 5
fixtures/   seeded test traffic + measured token shape     evidence/ terminal transcripts
tests/      lever, cost and deploy tests (api/tests = service tests)
```
No secrets are committed: `api/.env` is gitignored, and [evidence/no_secrets_check.txt](evidence/no_secrets_check.txt) shows the checks.
