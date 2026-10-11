"""The deploy configs agree with each other: ceilings, labels, budgets."""
from pathlib import Path

import yaml

import validate_budgets

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"


def test_budgets_agree_with_labels_and_cost_model():
    assert validate_budgets.main() == 0


def test_every_compose_service_has_limits_and_finops_labels():
    compose = yaml.safe_load((DEPLOY / "docker-compose.cost.yml").read_text())
    for name, svc in compose["services"].items():
        assert svc["deploy"]["resources"]["limits"]["memory"], name
        for key in ("afyaplus.service", "afyaplus.cost-center", "afyaplus.owner"):
            assert key in svc["labels"], (name, key)
        assert not svc["image"].endswith(":latest"), name


def test_replica_ceiling_is_the_same_everywhere():
    serverless = yaml.safe_load((DEPLOY / "serverless-ish.yaml").read_text())
    hpa = yaml.safe_load((DEPLOY / "hpa.yaml").read_text())
    assert serverless["interactive"]["max_instances"] == hpa["spec"]["maxReplicas"] == 3
    assert serverless["interactive"]["min_instances"] == hpa["spec"]["minReplicas"] == 1
    assert serverless["batch"]["min_instances"] == 0
