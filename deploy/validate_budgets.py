"""Check the cost controls agree with each other and with the cost model. Exits 1 on any drift.

    python deploy/validate_budgets.py

- Azure and AWS budgets: valid JSON, same cap, an 80% actual alert, a 100% forecast alert
- both filter on the service tag the compose file actually puts on the containers
- the cap traces to cost/cost_model_output.json: above the planned spike month's cloud
  spend (so a normal spike does not page anyone at 100%), and above baseline by enough that
  the 80% alert never fires in an ordinary month
"""
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CLOUD_LINES = ("containers", "logs")        # what an Azure/AWS budget can see; not OpenAI, not people


def main() -> int:
    errors = []
    az = json.loads((HERE / "azure_budget_triage.json").read_text())
    aws = json.loads((HERE / "aws_budget.json").read_text())
    aws_notify = json.loads((HERE / "aws_budget_notify.json").read_text())
    compose = yaml.safe_load((HERE / "docker-compose.cost.yml").read_text())
    model = json.loads((ROOT / "cost" / "cost_model_output.json").read_text())

    cap = az["amount"]
    if float(aws["BudgetLimit"]["Amount"]) != cap:
        errors.append(f"cap drift: azure {cap} vs aws {aws['BudgetLimit']['Amount']}")

    az_n = az["notifications"]
    az_actual = [n for n in az_n.values() if n["thresholdType"] == "Actual"]
    az_fcst = [n for n in az_n.values() if n["thresholdType"] == "Forecasted"]
    if [n["threshold"] for n in az_actual] != [80] or [n["threshold"] for n in az_fcst] != [100]:
        errors.append("azure: want one Actual 80% and one Forecasted 100% notification")
    aws_pairs = sorted((n["Notification"]["NotificationType"], n["Notification"]["Threshold"]) for n in aws_notify)
    if aws_pairs != [("ACTUAL", 80), ("FORECASTED", 100)]:
        errors.append(f"aws notifications {aws_pairs}, want ACTUAL 80 and FORECASTED 100")

    label = compose["x-finops-labels"]["afyaplus.service"]
    if az["filter"]["tags"]["values"] != [label]:
        errors.append(f"azure tag filter {az['filter']['tags']['values']} != compose label {label}")
    if aws["CostFilters"]["TagKeyValue"] != [f"user:service${label}"]:
        errors.append(f"aws tag filter {aws['CostFilters']['TagKeyValue']} != user:service${label}")

    def cloud(name_prefix: str) -> float:
        sc = next(s for s in model["scenarios"] if s["scenario"].startswith(name_prefix))
        return sum(sc["lines_usd"][k] for k in CLOUD_LINES)

    baseline, spike = cloud("baseline: no levers"), cloud("10x spike: no levers")
    if not spike <= cap:
        errors.append(f"cap ${cap} is below the planned spike month's cloud spend ${spike:.2f}")
    if not baseline < 0.8 * cap:
        errors.append(f"80% alert (${0.8 * cap:.2f}) would fire in an ordinary month (${baseline:.2f})")

    print(f"cap=${cap}/month on tag service={label} (azure + aws agree)")
    print(f"cloud spend from cost model: baseline ${baseline:.2f}, planned 10x spike ${spike:.2f}")
    print(f"80% actual alert at ${0.8 * cap:.2f}: silent in an ordinary month, fires late in a spike month")
    print(f"100% forecast alert: fires early in any month heading past ${cap}")
    for e in errors:
        print("FAIL:", e)
    print("budgets OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
