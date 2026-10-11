# Endpoint switch drill

Same image, same compose file, different model provider, chosen by two environment variables. Full transcript: `evidence/endpoint_switch_drill.txt`.

## Run A: default (OpenAI)
```
LLM_BASE_URL=            (empty = api.openai.com)
LLM_MODEL=gpt-4o-mini
```
`/health` → `"model":"gpt-4o-mini","llm_endpoint":"api.openai.com"`

## Run B: Nebius AI Studio shape
```
LLM_BASE_URL=https://api.studio.nebius.ai/v1
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```
`docker compose config` resolves both values. The running container's `/health` then reports `"model":"meta-llama/Meta-Llama-3.1-8B-Instruct","llm_endpoint":"api.studio.nebius.ai"`. The image id is the same in both runs (`286c151544d7`), with no rebuild and no code change. We did not send a triage call in Run B (no Nebius key); the drill proves the switch, not the provider. Azure OpenAI works the same way with its `https://<resource>.openai.azure.com/openai/v1` base URL.

The cache key includes the model name, so an answer from one model is never served as another model's.

## Bedrock
Bedrock is not OpenAI-compatible: it needs the AWS SDK and a different request shape. That means a thin adapter behind the same `triage_model()` interface, not a base-URL swap.
