# Two levers, measured before and after (Deliverable 3)

All runs were **live on gpt-4o-mini on 2026-10-11**, on fixed fixtures that anyone can regenerate (`python fixtures/make_fixtures.py`, seed 7). Total spend for every live run in this folder was about $0.01. Raw per-call data is in `levers/results/*.json`, and transcripts are in `evidence/`.

**p95** is the wait that 95 out of 100 requests were at or under. In other words, the slow end of what a clinician experiences. p50 is the typical wait.

## Lever 1: response cache (identical messages are answered once)

Code: `response_cache.py` (ships in the image, runs on every `/triage`); harness `levers/cache_triage.py`.
Fixture: `fixtures/traffic_100.json`, 100 calls of which 40 messages are unique and 60 are repeats. This is a *claimed* traffic mix. Real AfyaPlus repetition must be measured in production before this hit rate is quoted as fact.

| Same 100 calls | Before (cache off) | After (cache on) | Change |
|---|---:|---:|---:|
| Calls sent to the model | 100 | 40 | −60% |
| Cache hit rate | 0.00 | **0.60** (target ≥ 0.55; the script exits 1 below it) | |
| Tokens (prompt + completion) | 12,274 + 3,116 | 4,914 + 1,216 | −60% |
| **$ per 1,000 requests, tokens** | **$0.0371** | **$0.0147** | **−60%** |
| Typical wait (p50) | 975 ms | 0 ms (in-process hit) | |
| Slow end (p95) | 1,476 ms | 1,178 ms | −20% |
| Average wait | 1,043 ms | 418 ms | −60% |

`python levers/cache_hitrate.py --mode off` and `--mode on` → `evidence/lever1_cache_before_after.txt`

**Through the real service, two replicas sharing Redis** (`levers/http_replay.py --ports 8000,8002`): 100 of 100 returned 200, 60 HITs and 40 MISSes across both replicas, hit rate 0.60. A HIT took **10.6 ms at p95**, while a MISS took **1,005 ms at p50**. A message first seen on replica 1 was a HIT on replica 2 (`evidence/deploy_compose_run.txt`, `evidence/lever1_http_replay_two_replicas.txt`).

**Why the p95 barely moves:** 40% of calls are still misses, and a miss waits for the model. The cache makes the *typical* request instant. It cannot make the slowest requests faster until the hit rate passes 95%. We say so rather than quote the p50 alone.

**Replica effect** (`levers/replica_hit_simulation.py`, no API calls): if each replica keeps its own cache, the same traffic hits 0.60 on one replica, 0.36 on two and 0.30 on three. Redis keeps it at 0.60. Whether that is worth Redis's $23.43 a month is answered in `cost/cost_model.md`: not until about 2.6M requests a month.

### Quality note: cache
- **An exact-match cache cannot make an answer worse than the model would have given.** It returns an earlier answer, from the same model and prompt, to the same normalised message (case and spacing ignored) and county.
- It does freeze one answer for 10 minutes. At temperature 0, the model gave the same urgency to repeated messages 98.3% of the time. The exception was "Shortness of breath climbing stairs", answered `high` on some calls and `medium` on others. With the cache, whichever answer arrived first is repeated for 10 minutes. That gives consistency, not a new error, but it is worth knowing.
- The red-flag safety floor runs *before* an answer is stored, so a cached answer has already passed it. A failed model call is never cached. The key includes a hash of the system prompt, so changing the prompt can never serve an old prompt's answers.
- **No semantic ("similar enough") cache.** It would raise the hit rate, but it would answer "chest pain at rest" with the cached answer for "chest tightness at rest". For clinical triage we keep exact match only.

## Lever 2: batch queue for after-hours messages

Code: `levers/batch_worker.py` (SQLite queue, attempts, dead-letter after 3 tries). Before it calls the model, the worker reads the live cache, but it never writes to it. Measured with `levers/batch_measure.py`.
Fixture: `fixtures/backlog_24.json`, 24 after-hours SMS messages that a coordinator reads at 08:00. Nobody is waiting on these live.
**Before** is the same 24 messages answered one call each. These answers were already recorded live in the cache-off run, so no message was paid for twice.

| 24 messages | Model calls | Tokens (prompt + completion) | $ per 1,000 messages | Cost saving | Agreement with one-call answers |
|---|---:|---:|---:|---:|---:|
| Before: one call each | 24 | 2,946 + 741 | $0.0369 | | (one-call path agrees with itself on repeats: 0.98) |
| **Batch of 4 (recommended)** | 6 | 1,386 + 664 | **$0.0253** | **−31.6%** | **0.96** (1 of 24 differs) |
| Batch of 8 | 3 | 897 + 621 | $0.0211 | −42.8% | 0.92 (2 differ) |
| Batch of 12 | 2 | 734 + 602 | $0.0196 | −46.8% | 0.88 (3 differ) |

`evidence/lever2_batch_before_after.txt`. The same pattern (0.96 / 0.92 / 0.88, with the same messages differing) appeared on two separate live runs.

**Where the saving comes from:** the system prompt is paid once per batch instead of once per message, so prompt tokens fall by 53 to 75%. Completion tokens barely change, and they cost 4× more each. That is why a token saving of 44 to 64% becomes a dollar saving of 32 to 47%.

**OpenAI Batch API (documented, not used):** the same jobs submitted through the Batch API (results within 24 hours) are 50% off on top, which takes batch-of-4 to $0.0126 per 1,000 [1]. That fits an 08:00 deadline if the job is submitted by the evening before. We did not run it.

### Quality note: batch (this lever can degrade answers)
- **Bigger batches answer differently, and the differences lean the risky way.** At batch 8, both disagreements were downgrades from `medium` (see a clinician within 24 h) to `low` (self-care): "Insect bite with local swelling" and "Twisted ankle, mild swelling". At batch 12 a third message moved, "Child with diarrhoea since morning", up from `medium` to `high`.
- **So we recommend batch of 4.** It keeps 96% agreement, about the same as the one-call path's own 98% consistency, and keeps about three-quarters of the saving available at batch 8 (31.6% of 42.8%).
- Safeguards that stay on: the red-flag floor is applied per message after the batch reply, so a batch can never downgrade "chest pain" or "bleeding". A reply that misses or invents an id is rejected and retried, never half-saved. A poison batch is dead-lettered after 3 tries for a person to look at. Every after-hours message is still read by a coordinator at 08:00.
- n = 24 is a small sample. Agreement must be re-measured on real after-hours traffic before batch size is raised.

## Not done (declared)
- **Quantization or a smaller model:** not attempted. We have no GPU for this service, and two levers were measured instead. `cost/breakeven.py` shows why self-hosting a quantized model is not on the table at this volume.
- **Load at the spike:** one 0.5 vCPU replica carried about 31 requests a second with simulated 1-second model calls before p95 rose (`levers/load_test.py`, stub backend, free). A spike day peaks under 1 request a second, so the levers are about cost and wait time, not capacity.

[1] OpenAI pricing, see `cost/cost_model.md` footnote [1].
