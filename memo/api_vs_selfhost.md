# Memo: API-hosted vs self-hosted model for AfyaPlus triage

**To:** CTO, Finance · **From:** ML engineering · **Date:** 11 October 2026 · **Decision asked for:** where the triage model should run for the next 12 months

## Recommendation
**Stay on the hosted API (gpt-4o-mini) and revisit when one of the triggers below fires.** Self-hosting would turn a model bill of about **$2 a month** into a fixed **$830 to $3,860 a month**. It only breaks even at **26 to 120 million requests a month, 433 to 2,003 times today's volume.**

## The two paths
Both paths keep the same `/triage` service, login, rate limits and cache. Only the box behind `triage_model()` changes, which is the same switch the endpoint drill proved (`deploy/endpoint_switch_notes.md`).

| | API-hosted (today) | Self-hosted open model |
|---|---|---|
| Model | gpt-4o-mini via OpenAI | Llama 3 8B (our Week 4 fine-tune or the base model) on vLLM |
| How we pay | per token: $0.000037 per request [M] | per GPU-hour, whether or not anyone sends a message |
| Monthly at today's 60,000 requests | **$2.23** | **$834 to $3,861** fixed |
| Monthly at a 10× spike | $22.28 | the same fixed cost; one GPU still has capacity |
| Who keeps it running | OpenAI | us: GPU drivers, vLLM upgrades, capacity, a 03:00 page |

## Break-even
Self-hosting wins when `fixed + var × N < API price × N`, so **N = fixed ÷ (API price per request − self-host variable cost)**.

| Self-host option (on-demand, checked 2026-10-11) | Fixed per month: GPU (730 h) + on-call $400 + storage $50 | Break-even (requests/month) | × today |
|---|---:|---:|---:|
| Azure A10 (24 GB), South Africa North [2] | $3,861 | 120.2 M | 2,003× |
| Azure A10, East US [2] | $2,786 | 86.7 M | 1,445× |
| Azure T4 (16 GB), East US [2]: 8B fits only 4-bit | $834 | **26.0 M** | **433×** |
| vast.ai RTX 4090, what we paid in Week 4 [4]: no SLA, not production | $1,019 | 31.7 M | 529× |

Source: `python cost/breakeven.py` → `cost/breakeven_output.json`. Self-host variable cost: $0.000005 per request [A].

**Pressure tests (same script):**
- *Price on-call at $0* (the dishonest version): the cheapest option still needs 13.5 M a month.
- *A second GPU for redundancy* (a clinical service should not have a single point of failure): break-even rises to 38 to 226 M.
- *If we paid gpt-4o prices instead* (16.7× per token [1]): break-even falls to 1.4 to 6.3 M a month. That is still **23 to 105× today**.

## Assumptions, and what we did not do
- **Estimated, not run.** We have not served this workload on our own GPU. GPU prices are list prices [2]; the RTX 4090 rate is what we actually paid in Week 4 [4], for training, not serving. People ($400 a month of on-call) and storage ($50) are the course's honest defaults [A], not quotes.
- GPUs are billed all month. A clinician cannot wait minutes for an 8B model to load, so scale-to-zero is not available on the interactive path.
- One GPU is enough for capacity: one 8B model on an A10 or T4 serves far more than our peak of under 1 request a second. The cost is the always-on box, not the throughput.
- **Quality is unknown, not equal.** Our Week 4 fine-tune beat its own base model (judge score 4.09 vs 1.86). Its first training run gave paracetamol dosing for a fever question until we added refusal examples. It has never been compared with gpt-4o-mini on the triage task. Switching would need that evaluation and the red-flag safety floor first, whatever the cost.

## What would change the decision
1. **Volume** grows past about 26 M requests a month for a sustained period. At today's growth we are nowhere near this.
2. **Price**: gpt-4o-mini is withdrawn or reprices to gpt-4o levels *and* volume passes about 1.4 M a month.
3. **Data residency**: if the Kenya Data Protection Act review (Week 9) rules that patient messages may not leave a given jurisdiction, cost stops being the deciding factor. The first step would then be a hosted model in-region, such as Azure OpenAI in South Africa North, through the same `LLM_BASE_URL` switch. That is cheaper than owning GPUs.
4. **A GPU we already pay for**: if AfyaPlus already runs a GPU for other work, the fixed cost is shared and break-even falls.
5. **Quality**: if an open model, evaluated on our triage set, is clearly safer or better for Kenyan clinical language.

## Middle paths worth knowing
- **Hosted open weights** (Nebius AI Studio and similar): pay per token for Llama 3 with no GPU operations, using the same base-URL switch. This is the cheapest way to *test* the open model's quality before ever buying GPU hours.
- **OpenAI Batch API** for the after-hours queue: 50% off, with no infrastructure change (`levers/measurements.md`).

[1] OpenAI pricing · [2] Azure Retail Prices API · [4] Week 4 capstone runbook. Full citations: `cost/cost_model.md`.
