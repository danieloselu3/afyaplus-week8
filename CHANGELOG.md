# Changelog: AfyaPlus triage platform

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/). Versioning: [SemVer](https://semver.org/).

**One release number, everywhere (lockstep).** A release `X.Y.Z` is the git tag `vX.Y.Z`, the image tag `afyaplus-triage:X.Y.Z`, the prompt bundle (`prompts/pin.json` `bundle_version`) and the MCP server's `version://current`. The number comes from `config/triage.yaml` `release`, and `scripts/check_release.py` fails CI if any of them disagree. A component that did not change still moves with the release; its section below says "no changes".

**Bump rules, applied to the release as a whole:**

| Change | Bump |
|---|---|
| Rename or remove a required field or tool, or change a response shape | MAJOR |
| Additive: a new tool, a new optional field, or a new prompt behind a flag | MINOR |
| Docstring or wording fixes with no behaviour change | PATCH |

**Prompt versions are content versions,** not release versions. `prompts/triage_system_v1.2.0.txt` is a piece of text, and a release's bundle pins one or more of them by sha256. A pinned prompt file is never edited. A change is a new file.

## [Unreleased]

### Breaking (draft, not shipped)
- **MCP `check_stock`:** rename the argument `item` to `item_code` (it would carry a stock code such as `ORS-200`).
  - Every agent that cached the current schema would break on every call, so this needs **2.0.0**.
  - Plan: in a 1.x minor, accept both names and log a deprecation warning for `item`. Remove `item` in 2.0.0, and no earlier than 30 days after partners are told.
  - CI blocks the rename until then: `scripts/check_mcp_health.py` requires `check_stock` with its current shape.

## [1.3.0] - 2026-10-11
### Added
- **Versioned prompts:**
  - The triage system prompt moved out of code into `prompts/triage_system_v1.2.0.txt`, byte-identical to the Week 6/7 string.
  - It is pinned by sha256 in `prompts/pin.json` (bundle 1.3.0).
  - The service refuses to start if the file on disk does not match its pin (`prompt_app.py`).
- **Versioned run config:** `config/triage.yaml` holds model, temperature, limits, prompt version and release. `PROMPT_VERSION` overrides it, so a prompt rollback is a config change on the same image.
- **`/health` reports** `prompt_version`, `prompt_sha256`, `candidate`, `config_sha256`, `model_version`, `image_tag` and `git_sha`. `/triage` echoes `prompt_version`.
- **Image identity:** `IMAGE_TAG` and `GIT_SHA` build args, plus OCI revision and source labels.
- **MCP server 1.3.0** (`logistics_mcp_versioned.py`, which wraps the untouched Week 6 server):
  - `version://current` resource
  - `list_low_stock(clinic_id)` tool. This is additive, and no existing tool schema changed.
- **CI gates:** `check_prompt_pin.py`, `scripts/check_release.py`, `eval_prompts.py` (golden set, threshold 0.85, quarantine capped at 5%), `scripts/check_mcp_health.py` (stdio handshake plus a real call). GitHub Actions runs lint-test, then eval, then mcp-health, then build, then deploy; `azure-pipelines.yml` is the twin.

### Changed
- The model is pinned to the dated snapshot `gpt-4o-mini-2024-07-18` instead of the moving alias `gpt-4o-mini`. The alias pointed at this snapshot on 2026-10-11, so answers are unchanged.
- The response cache keys on the served prompt's sha256, so a new prompt never receives another prompt's cached answer.
- The logistics agent spawns the versioned MCP server.
- `docker-compose.yml` image tags were still `1.1.0` from Week 6. They are now aligned to the release, and CI keeps them aligned.

### MCP server
- 1.0.0 → 1.3.0: added `version://current` and `list_low_stock`, both additive. The jump to 1.3.0 is the lockstep alignment. There was no MCP 1.1.0 or 1.2.0.

## [1.2.0] - 2026-10-11 (Week 7, repo afyaplus-week7)
### Added
- Response cache (lever 1), after-hours batch queue (lever 2), cost model, budget alerts, and the `LLM_BASE_URL` endpoint switch.

## [1.1.0] - 2026-09-27 (Week 6, repo afyaplus-platform)
### Added
- FastAPI triage service with JWT and roles, a Docker image, the logistics MCP server (MCP 1.0.0: `check_stock`, `plan_delivery_route`, `get_delivery_eta`, `clinics://` resources) and the logistics agent.
