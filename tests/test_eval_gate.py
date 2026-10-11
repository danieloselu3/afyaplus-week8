import json

import eval_prompts as ev

CASE = {"id": "t1", "message": "x", "expected_urgency": "medium",
        "must_include_any": ["clinic", "clinician"], "must_not": ["you have malaria"]}


def test_a_good_answer_passes():
    ok, quality, safety = ev.check_case(
        {"urgency": "medium", "advice": "Please see a clinician within 24 hours."}, CASE)
    assert ok and not quality and not safety


def test_wrong_label_is_a_quality_miss_not_a_safety_failure():
    ok, quality, safety = ev.check_case(
        {"urgency": "low", "advice": "Please see a clinician within 24 hours."}, CASE)
    assert not ok and quality and not safety


def test_a_dose_is_a_safety_failure_on_any_case():
    ok, _quality, safety = ev.check_case(
        {"urgency": "medium", "advice": "Take 500 mg paracetamol and see a clinician."}, CASE)
    assert not ok and len(safety) == 2


def test_null_expected_urgency_scores_properties_only():
    case = {**CASE, "expected_urgency": None}
    ok, _q, _s = ev.check_case({"urgency": "high", "advice": "See a clinician."}, case)
    assert ok


def test_committed_tree_passes_the_gate(monkeypatch):
    monkeypatch.setattr("sys.argv", ["eval_prompts.py"])
    assert ev.main() == 0


def test_missing_fixture_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESPONSES", tmp_path)                 # no recordings at all
    monkeypatch.setattr("sys.argv", ["eval_prompts.py"])
    assert ev.main() == 1


def test_safety_failure_blocks_even_above_threshold(tmp_path, monkeypatch):
    import prompt_app
    sha = prompt_app.PROMPT_SHA256
    real = json.loads((ev.RESPONSES / f"{sha}.json").read_text(encoding="utf-8"))
    real["by_id"]["g19"]["advice"] = "Rest, drink water and take 2 panadol."     # one bad answer
    (tmp_path / f"{sha}.json").write_text(json.dumps(real), encoding="utf-8")
    monkeypatch.setattr(ev, "RESPONSES", tmp_path)
    monkeypatch.setattr("sys.argv", ["eval_prompts.py"])
    assert ev.main() == 1


def test_quarantine_over_cap_fails(tmp_path, monkeypatch):
    q = tmp_path / "quarantine.json"
    q.write_text(json.dumps({"ids": ["g20", "g21", "g22"]}))                   # 10% > 5%
    monkeypatch.setattr(ev, "QUARANTINE", q)
    monkeypatch.setattr("sys.argv", ["eval_prompts.py"])
    assert ev.main() == 1
