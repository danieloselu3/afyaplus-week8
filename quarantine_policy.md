# Flaky-case quarantine policy (eval gate)

**What quarantine is for.** It covers a golden case whose recorded answer flips between runs for a reason that is not the prompt, such as the model's own variance on a borderline message. A quarantined case is still scored and printed on every run (`eval_prompts.py` shows it as `[quarantined]`). It just does not count toward `eval_score`.

**What quarantine is not for.** It does not hide a real regression, and it does not hide a case whose label we disagree with. A wrong label is fixed in `evals/golden.jsonl` through a reviewed pull request, and the answers are then re-recorded. **A safety case can never be quarantined**: dose-fishing, the injection probe, or anything that tests `must_not`.

| Rule | Value | Enforced by |
|---|---|---|
| Maximum share of the set | **5%** (1 of 30 today) | `eval_prompts.py`: `MAX_QUARANTINE_RATE`, exit 1 above it |
| Unknown ids in the list | fail | `eval_prompts.py` |
| Who may add a case | a PR approved by clinical_ops **and** ml-eng (CODEOWNERS on `fixtures/`) | branch protection |
| How a case graduates | it passes in **3 consecutive** recordings (three runs of `scripts/record_responses.py` on the same prompt) | the PR that removes it attaches the three recordings |
| Review | every sprint review lists the quarantine; anything over 2 sprints old is fixed or deleted | Definition of Done (`runbook.md`) |

**Today:** the list is empty. The two 1.2.0 misses, g11 and g29, are *not* quarantined. They are consistent over-triage (`high` where the label says `medium`), not flakes, and they are visible in every eval run.
