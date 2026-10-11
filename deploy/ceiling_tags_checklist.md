# Ceiling and tags checklist

Two questions a stranger can answer from these files alone: **who owns this bill?** and **what stops it growing?**

## Who owns the bill: one set of tag keys, used everywhere
| Compose label (`docker-compose.cost.yml`) | Azure tag | AWS cost-allocation tag | Value |
|---|---|---|---|
| `afyaplus.service` | `service` | `user:service` | `triage-api` |
| `afyaplus.version` | `version` | `user:version` | `1.2.0` |
| `afyaplus.env` | `env` | `user:env` | `staging` (production in `serverless-ish.yaml`) |
| `afyaplus.cost-center` | `cost-center` | `user:cost-center` | `clinical-ai` |
| `afyaplus.owner` | `owner` | `user:owner` | `danieloselu3` |

The same labels are baked into the image (`Dockerfile` `LABEL`) and checked at runtime in `evidence/deploy_compose_run.txt` (`docker inspect`). The Redis container carries them too, plus `afyaplus.component: response-cache`.

**The budget link:** both budgets filter on `service = triage-api`: Azure with `filter.tags`, AWS with `user:service$triage-api`. `deploy/validate_budgets.py` fails if the label and the two filters ever disagree. A budget whose tag matches nothing is the quiet failure the Tuesday lab warns about.

## What stops it growing
| Ceiling | Value | Declared in |
|---|---|---|
| CPU per replica | 0.5 vCPU | `docker-compose.cost.yml` `deploy.resources.limits`, `serverless-ish.yaml` |
| Memory per replica | 1 GiB limit, 256 MiB reserved | the same |
| Replicas | min 1, **max 3** | `serverless-ish.yaml` `max_instances`, `hpa.yaml` `maxReplicas` |
| Redis memory | 64 MB, LRU eviction, no persistence | `docker-compose.cost.yml` |
| Calls per coordinator | 30 a minute (Week 6 default 5; raised for clinic batches) | `TRIAGE_RATE_LIMIT_PER_MIN` |
| Model retries | 1 | `triage_model.py` `max_retries=1` |
| Answer length | 150 tokens | `triage_model.py` `max_tokens=150` |
| Monthly cloud spend | $80 cap, alerts at 80% actual and 100% forecast | `azure_budget_triage.json`, `aws_budget*.json` |

Why max 3 replicas: one replica carried about 31 requests a second before saturating (`levers/results/load_test.json`), and a spike day peaks under 1 request a second. Three replicas cover a zone failure and a burst. A retry storm hitting the ceiling queues; it does not multiply the bill.
