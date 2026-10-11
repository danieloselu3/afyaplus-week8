# Budget alert: triage-api

Files: `azure_budget_triage.json`, `aws_budget.json` and `aws_budget_notify.json` define the alerts. `python deploy/validate_budgets.py` proves they agree with each other, with the compose labels and with the cost model. **Not applied to a live subscription.** We have no paid Azure or AWS account, so these are submitted as config (a declared fallback). The Azure file follows the `Microsoft.Consumption/budgets` request body. The AWS pair is what `aws budgets create-budget --budget file://aws_budget.json --notifications-with-subscribers file://aws_budget_notify.json` takes.

## Cap: $80 a month
A cloud budget can only see cloud resources: the container and the logs. From `cost/cost_model.md`, those come to **$34.42 in an ordinary month** and **$77.47 in a planned 10× spike month** (two replicas). The cap is the spike month rounded up. A spike we planned for therefore stays under 100%, and anything beyond it does not.

## Thresholds: 80% actual, 100% forecast
- **80% actual ($64)** never fires in an ordinary month, because $34 is far below it. In a spike month spend runs at about $2.58 a day, so the alert fires around day 25. That leaves five days of the same billing month to act, and confirms the spike is real.
- **100% forecast ($80)** fires early in any month heading past the cap. An example is three replicas stuck at their ceiling, about $113 a month. A forecast alert arrives in the first days; an actual-spend alert would only arrive after the money is gone.

## Who receives it
`finops@afyaplus.example` is the finance rota. `triage-oncall@afyaplus.example` is the engineer on the triage service, who can change the burn rate and not only report it. (These are placeholder `.example` addresses. Real aliases are set at apply time.)

## The one action
When the 80% alert fires, on-call checks the request log (`logs/triage_api.log`, grouped by coordinator) for a loop.

**If one client is looping, lower `TRIAGE_RATE_LIMIT_PER_MIN` from 30 to 10** and redeploy. That is a config change with no rebuild. The cost is that a busy honest coordinator may wait up to a minute between bursts. If the traffic is a real spike, do nothing: it was planned and priced.

## What these budgets do NOT cover
- **The OpenAI bill** goes to OpenAI, not Azure or AWS. Set a monthly budget on the OpenAI project, $25, at platform.openai.com (Settings → Limits). That covers the spike month's $22.28 of tokens with no levers. **We have not configured this. It is a manual step for whoever owns the key.**
- **People time** ($150 a month in the model) is not a cloud line at all.
