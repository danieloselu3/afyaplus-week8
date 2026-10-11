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
