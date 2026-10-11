# CI runs (GitHub Actions, public)

All runs: https://github.com/danieloselu3/afyaplus-week8/actions

| When | Event | Result | What it shows | Run |
|---|---|---|---|---|
| main @ 95e199a | push | ✅ lint-test, eval, mcp-health, build, deploy-staging | First green pipeline. Image pushed to GHCR; staging pulled `sha256:d7c55345…` by digest | [38158789727](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38158789727) |
| tag v1.3.0 | push | ❌ deploy-production (gates, build and staging ✅) | The production job lacked dependencies, so promotion failed and production did not change | [38159038225](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38159038225) |
| PR #1 hotfix | pull_request | ✅ all four required checks | The fix went through a PR (direct push rejected) | [38159527371](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38159527371) |
| tag v1.3.1 | push | ✅ all six jobs | Promoted to production: "running image is release 1.3.1 at commit dcb916c, prompt 1.2.0" | [38159724713](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38159724713) |
| PR #2 (demo) | pull_request | ❌ mcp-health; build/deploy skipped; merge BLOCKED | MCP gate catches a transport change that all unit tests pass | [38160162563](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38160162563) |
| PR #3 draft | pull_request | ❌ eval; later jobs skipped; merge BLOCKED | Eval gate: score 0.90 above the bar, but 2 safety failures (paracetamol dose) | [38160700091](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38160700091) |
| PR #3 revised | pull_request | ✅ all four required checks | Candidate 0.93, 0 safety failures; merge state CLEAN | [38161154455](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38161154455) |
| main @ ae7155d (PR #3 merged) | push | ✅ gates, build, deploy-staging | Canary deployed to staging; `--expect-config` confirms A=1.2.0 and B=1.3.0-candidate at 10% | [38161557409](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38161557409) |
| tag v1.4.0 | push | ✅ all six jobs | Promoted to production: `sha256:0f8f7207c345…` (the same digest for `1.4.0-ae7155d` and `1.4.0`); "running image is release 1.4.0 at commit ae7155d"; both variants match pin and config | [38161578904](https://github.com/danieloselu3/afyaplus-week8/actions/runs/38161578904) |

**Releases:**

| Release | Status | Production image |
|---|---|---|
| v1.3.0 | never reached production (incident) | none |
| v1.3.1 | promoted | `ghcr.io/danieloselu3/afyaplus-triage:1.3.1` |
| **v1.4.0** | **current** | `ghcr.io/danieloselu3/afyaplus-triage@sha256:0f8f7207c345e4c919830a4123d1be05b912a45978be3cfce53219fa079055de` |
