# Cost model: AfyaPlus triage API (Deliverable 1)

Every number on this page is printed by a script you can re-run:

```
python cost/cost_model.py      # the table below -> cost/cost_model_output.json
python cost/sensitivity.py     # what moves the bill
python cost/retry_storm.py     # the incident line
```

Footnotes: **[1]–[4]** are published prices, **[M]** is measured by us, and **[A]** is an assumption we chose. An [A] is not a fact. It is the number to argue with.

## The answer

| | Requests a month | Monthly total | **$ per 1,000 requests, all-in** | $ per 1,000, model tokens only |
|---|---:|---:|---:|---:|
| Today's traffic, no levers | 60,000 | $186.65 | **$3.11** | $0.0371 |
| Today's traffic, cache + batch (recommended) | 60,000 | $185.26 | **$3.09** | $0.0139 |
| 10× spike, no levers | 600,000 | $249.75 | **$0.42** | $0.0371 |
| 10× spike, cache on each replica + batch (recommended) | 600,000 | $240.83 | **$0.40** | $0.0223 |
| 10× spike, shared Redis cache + batch | 600,000 | $259.25 | $0.43 | $0.0139 |

**One request costs about $0.0031 all-in today.** The model's share of that is $0.000037, about 1%.

Three things a reader should take from the table:

1. **The model is the cheapest line.** At today's traffic the gpt-4o-mini bill is about $2 a month. The month is made up of people ($150 [A]) and an always-on container ($34 [2][3]).
2. **A spike makes each request cheaper, not dearer.** Fixed costs are spread over ten times the traffic. The monthly bill rises by about $55 to $63. The cost per 1,000 requests falls from $3.11 to $0.42.
3. **The levers cut the token line by 40 to 63%,** but they barely move the total, because tokens are a small part of it. Their bigger value is speed (a cached answer returns in about 10 ms instead of about 1 s). They also protect us against a model price rise (see the sensitivity section).

## The lines, and where each number comes from

### Model tokens
| Input | Value | Source |
|---|---|---|
| Model | gpt-4o-mini | the Week 6 service |
| Prompt price | $0.15 per 1M tokens | [1] |
| Completion price | $0.60 per 1M tokens | [1] |
| Batch API discount (documented, not used) | 50% | [1] |
| Prompt tokens per request | 122.7 | [M] 100 live calls, `fixtures/usage_recorded.json` |
| Completion tokens per request | 31.2 | [M] same run |
| **Cost per model call** | **$0.000037** | 122.7 × 0.15/1M + 31.2 × 0.60/1M |

The course's teaching shape was 450 prompt / 180 completion tokens ($0.0001755 a call). Our real prompts and answers are about a quarter of that, because the Week 6 prompt is short and the answer is capped at two sentences. Pricing from the course shape would have overstated the token bill by about 4.7×.

### Infrastructure (Azure, South Africa North, the nearest Azure region to Kenya)
| Line | Rate | Source | Baseline | Spike |
|---|---|---|---:|---:|
| Container Apps, always-on replica, 0.5 vCPU / 1 GiB | $0.000024 per vCPU-s, $0.000003 per GiB-s, after the monthly free grant | [2][3] | 1 replica: $34.02 | 2 replicas: $73.44 |
| Container Apps requests | $0.40 per 1M after 2M free | [2][3] | $0 | $0 |
| Redis Basic C0 (only in the Redis row) | $0.0321 an hour | [2] | – | $23.43 |
| Log ingestion | $3.36 per GB, free tier not assumed | [2] | $0.40 | $4.03 |
| Log size per request | about 2 KB (request, model and audit lines) | [A] | | |

Conservative choice: the always-on replica is billed at the active rate for the whole month. Container Apps actually charges a lower idle rate between requests, so the real bill is lower. We keep one replica always on (`min_instances: 1`) so a clinician never waits for a cold start.

### People
| Line | Value | Source |
|---|---|---|
| On-call checks, prompt review, budget-alert triage | 6 hours a month | [A] |
| Loaded hourly cost, mid-level engineer, Nairobi | $25 | [A], a teaching figure, not AfyaPlus payroll |
| **Monthly** | **$150** | |

### Incidents
A retry storm is a buggy client that retries with no backoff: 5% of requests, 4 extra billed attempts each. It multiplies the token line by **1.20 at any volume** (`cost/retry_storm.py`). That is $0.44 a month today and $4.45 at the spike. The dollars are small because tokens are small. The real cost is honest clinicians being rate-limited, plus an on-call hour. The controls already in place are a per-coordinator rate limit with `Retry-After`, an OpenAI client with `max_retries=1`, and the budget alerts in `deploy/`.

### Traffic
| Assumption | Value | Source |
|---|---|---|
| Today's traffic | 2,000 triage requests a day | [A] chosen at planning |
| Month | 30 days, so 60,000 requests | [A] |
| Spike | 10×: 20,000 a day for a whole month (for example an outbreak) | [A] |
| Replicas | 1 at baseline, 2 during the spike (capacity is not the reason, one replica handles it; the second is for resilience) | [A] |
| After-hours share (batchable) | 20% of messages | [A] |
| Cache hit rate | 0.60 with one shared cache; 0.36 with two separate per-replica caches | [M] on the fixture; real traffic must be measured |
| Batch saving (batch size 4) | 31.6% of the token cost of those messages | [M] `levers/results/batch.json` |

## Sensitivity: what moves the bill (`cost/sensitivity.py`)

| If this changes… | Monthly total at baseline | At the spike |
|---|---:|---:|
| Nothing (the no-levers row) | $186.65 | $249.75 |
| Model price doubles | $188.88 | $272.02 |
| We switch to gpt-4o (16.7× the price) [1] | $221.62 | $599.46 |
| People time goes from 6 to 12 hours | $336.65 | $399.75 |
| People time falls to 2 hours | $86.65 | $149.75 |
| Cache hit rate 0 → 0.60 | $185.31 | $236.38 |

**People time moves the bill most. Model price is second, and only in a spike.** The cache matters most if the price per token goes up: at gpt-4o prices, a shared cache at 0.60 saves $223 of tokens in a spike month ($134 with two separate caches at 0.36).

## Why we do not recommend Redis yet

Redis lets every replica share one cache. On the fixture it keeps the hit rate at 0.60 across two replicas, where two separate in-process caches manage 0.36 (`levers/replica_hit_simulation.py`). That difference is worth less than Redis costs until traffic reaches about **2.6 million requests a month (about 88,000 a day)**, 44× today's volume. This volume is printed by `cost/cost_model.py`. Below it, each replica keeps its own cache. The Redis path is built, tested and evidenced over HTTP across two replicas (`evidence/deploy_compose_run.txt`), so it can be turned on with one environment variable when volume justifies it.

## Footnotes
- [1] OpenAI API pricing, gpt-4o-mini model page (https://developers.openai.com/api/docs/models/gpt-4o-mini): $0.15 per 1M input tokens, $0.60 per 1M output tokens; the Batch API is 50% off both. gpt-4o: $2.50 and $10.00 per 1M. Checked 2026-10-11.
- [2] Azure Retail Prices API (https://prices.azure.com/api/retail/prices), pay-as-you-go, retrieved 2026-10-11:
  - Container Apps Standard, South Africa North: vCPU active $0.000024 per second, memory $0.000003 per GiB-second, requests $0.40 per 1M.
  - Redis Cache Basic C0: $0.0321 an hour.
  - Log Analytics ingestion: $3.36 per GB.
  - GPU VMs (used in the memo): NV36ads A10 v5 at $4.672 an hour (South Africa North) and $3.20 an hour (East US); NC4as T4 v3 at $0.526 an hour (East US).
- [3] Azure Container Apps pricing page (https://azure.microsoft.com/en-us/pricing/details/container-apps/): the first 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests each month are free.
- [4] Week 4 capstone (`lab/wk4/.../RUNBOOK_VASTAI.md`): a vast.ai RTX 4090 actually rented at $0.78 an hour.
- [M] Measured in this repo on 2026-10-11. See `levers/measurements.md`.
- [A] Assumption. Change the constant in `cost/cost_model.py` and re-run; every table here follows.
