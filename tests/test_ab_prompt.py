import json
import subprocess
import sys

from fastapi.testclient import TestClient

import ab_metrics
import ab_report
import prompt_app
import triage_api
from ab_prompt_flag import assign_variant, bucket, select_prompt

client = TestClient(triage_api.app)


def login():
    r = client.post("/token", json={"username": "mercy", "password": "logistics2026"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_bucket_is_the_same_in_another_process():
    """sha256, not hash(): a fresh interpreter (new hash seed) must agree."""
    out = subprocess.run([sys.executable, "-c", "from ab_prompt_flag import bucket; print(bucket('Migori'))"],
                         capture_output=True, text=True, cwd=prompt_app.ROOT, check=True)
    assert int(out.stdout.strip()) == bucket("Migori") == 8


def test_assignment_is_sticky_and_case_insensitive():
    assert {assign_variant(k, 10) for k in ("Migori", "migori ", "MIGORI")} == {"B"}
    assert assign_variant("Kisumu", 10) == "A"


def test_pct_is_a_strict_bucket_boundary():
    # Migori is bucket 8: inside a 9% slice (buckets 0-8), outside an 8% slice (0-7).
    assert bucket("Migori") == 8
    assert assign_variant("Migori", 9) == "B"
    assert assign_variant("Migori", 8) == "A"


def test_the_synthetic_split_lands_in_band():
    counts = {"A": 0, "B": 0}
    for i in range(100):
        counts[assign_variant(f"user-{i}", 20)] += 1
    assert 15 <= counts["B"] <= 25


def test_configured_canary_serves_its_slice_through_the_api(tmp_path, monkeypatch):
    monkeypatch.setattr(ab_metrics, "LOG", tmp_path / "ab.jsonl")
    headers = login()
    b = client.post("/triage", json={"patient_message": "Mild cough for two days", "county": "Migori"},
                    headers=headers)
    a = client.post("/triage", json={"patient_message": "Mild cough for two days", "county": "Kisumu"},
                    headers=headers)
    assert b.headers["X-Prompt-Variant"] == "B" and b.json()["prompt_version"] == prompt_app.CANDIDATE_VERSION
    assert a.headers["X-Prompt-Variant"] == "A" and a.json()["prompt_version"] == prompt_app.PROMPT_VERSION
    rows = [json.loads(line) for line in (tmp_path / "ab.jsonl").read_text().splitlines()]
    assert [r["variant"] for r in rows] == ["B", "A"]
    assert all("cough" not in json.dumps(r) for r in rows)              # no patient text in metrics


def test_variants_never_share_a_cached_answer():
    _v, _p, _t, sha_b = select_prompt("Migori")
    _v, _p, _t, sha_a = select_prompt("Kisumu")
    assert sha_a != sha_b
    import response_cache
    assert response_cache.make_key("x", "c", sha_a) != response_cache.make_key("x", "c", sha_b)


def test_health_reports_the_canary():
    cand = client.get("/health").json()["candidate"]
    assert cand == {"prompt_version": prompt_app.CANDIDATE_VERSION, "prompt_sha256": prompt_app.CANDIDATE_SHA256,
                    "traffic_pct": prompt_app.CANDIDATE_PCT}


def test_report_lists_the_counties_on_the_candidate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["ab_report.py"])
    assert ab_report.main() == 0
    report = json.loads((tmp_path / "ab_report.json").read_text())
    assert "Migori" in report["live_config"]["counties_on_B"] and len(ab_report.COUNTIES) == 47
