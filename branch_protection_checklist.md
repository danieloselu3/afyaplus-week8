# Branch protection checklist: afyaplus-week8 `main`

Applied with `gh api` on 2026-10-11. The settings as returned by GitHub are in [evidence/branch_protection/main_protection.json](evidence/branch_protection/main_protection.json) and [tag_ruleset.json](evidence/branch_protection/tag_ruleset.json).

## Rules
| Rule | Setting | Evidence |
|---|---|---|
| Pull request required before merging | **Yes** | `required_pull_request_reviews` present. A direct push was rejected with "Changes must be made through a pull request" ([direct_push_and_tag_delete_rejected.txt](evidence/branch_protection/direct_push_and_tag_delete_rejected.txt)) |
| Required approving reviews | **0** (solo repo: the author cannot approve their own PR). In the team: **1**, plus CODEOWNERS review on `prompts/`, `config/`, `evals/`, `fixtures/` | `.github/CODEOWNERS`; declared in the README |
| Required status checks | **`lint-test`, `eval`, `mcp-health`, `build`**, strict (the branch must be up to date with `main`) | Names copied from completed runs. PR #3 was blocked by `eval`, and PR #2 by `mcp-health` |
| Administrators included (no bypass) | **Yes** (`enforce_admins: true`). The owner's own push was rejected | [direct_push_and_tag_delete_rejected.txt](evidence/branch_protection/direct_push_and_tag_delete_rejected.txt) |
| Force pushes / branch deletion | **Disabled** / **disabled** | `allow_force_pushes: false`, `allow_deletions: false` |
| Conversations resolved before merge | **Yes** | `required_conversation_resolution: true` |
| Release tags `v*` immutable | **Yes**: a ruleset blocks deleting or moving them, with no bypass actors | Deleting `v1.3.0` was rejected ("Cannot delete this tag") |

## Incident mapping: which rule stops which failure
- **A prompt edit that gives medicine doses** (PR #3's first draft, eval 0.90 but 2 safety failures). The required check `eval` was red, so the merge button stayed disabled ([eval_gate_blocks_candidate_pr.txt](evidence/eval_gate_blocks_candidate_pr.txt)). Without the required check, it would have been one click away from 10% of counties.
- **A change that breaks the agent's tools while every unit test passes** (PR #2, the MCP server moved to HTTP transport). `mcp-health` was red and `build`/`deploy` never started ([mcp_health_failing_pr.txt](evidence/mcp_health_failing_pr.txt)).
- **"Just push the hotfix to main"** (the v1.3.0 promotion failure). Direct push is impossible, even for an admin, so the fix went through PR #1 and every gate.
- **"Move the v1.3.0 tag to the fixed commit"**. The tag ruleset forbids it, so the fix became v1.3.1 and v1.3.0 still names exactly what was tested.
- **A stale branch merging after main moved** (for example, two prompt PRs at once). Strict status checks require the PR to be re-tested on top of the latest `main`.
- **Clinical wording approved by someone without clinical accountability**. In the team, CODEOWNERS makes clinical_ops a required reviewer on `prompts/` and `config/`. Here, both roles are the owner (declared).

## What is not protected (declared)
- Reviews: 0 required, a solo-repo limitation. It would be 1 + CODEOWNERS in a team.
- The `staging` and `production` GitHub environments exist but have **no required reviewers**. In the team, production would require clinical_ops + ml-eng approval before `deploy-production` runs.
