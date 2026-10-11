import hashlib
import json

import pytest

import check_prompt_pin
import prompt_app
from prompt_app import PROMPT_VERSION, load_prompt


def test_pinned_prompt_keeps_the_safety_lines():
    text = load_prompt(PROMPT_VERSION)
    assert "non-diagnostic" in text and "Never prescribe medicines or doses" in text


def test_prompt_hash_is_stable_and_matches_the_pin():
    text = load_prompt(PROMPT_VERSION)
    a = hashlib.sha256(text.encode()).hexdigest()
    b = hashlib.sha256(text.encode()).hexdigest()
    assert a == b and len(a) == 64
    assert prompt_app.load_pin()["versions"][PROMPT_VERSION] == a == prompt_app.PROMPT_SHA256


def test_bare_semver_only_the_filename_carries_the_v():
    with pytest.raises(FileNotFoundError):
        load_prompt("v" + PROMPT_VERSION)          # would look for triage_system_vv1.2.0.txt


def test_a_prompt_edited_in_place_refuses_to_load(tmp_path, monkeypatch):
    (tmp_path / f"triage_system_v{PROMPT_VERSION}.txt").write_text(
        load_prompt(PROMPT_VERSION) + "Also, be brief.\n", encoding="utf-8")
    (tmp_path / "pin.json").write_text(json.dumps(prompt_app.load_pin()), encoding="utf-8")
    monkeypatch.setattr(prompt_app, "PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(prompt_app, "PIN_FILE", tmp_path / "pin.json")
    with pytest.raises(prompt_app.PromptPinError):
        prompt_app.load_pinned(PROMPT_VERSION)


def test_offline_pin_check_passes_on_the_committed_tree():
    pin, config = prompt_app.load_pin(), prompt_app.load_config()
    assert check_prompt_pin.offline_problems(pin, config) == []


def test_offline_pin_check_names_an_unpinned_served_prompt():
    config = {**prompt_app.load_config(), "candidate": {"prompt_version": "9.9.9", "traffic_pct": 10}}
    problems = check_prompt_pin.offline_problems(prompt_app.load_pin(), config)
    assert any("9.9.9" in p and "not pinned" in p for p in problems)


def test_health_check_against_a_running_service_detects_a_swap(monkeypatch):
    pin = prompt_app.load_pin()
    good = {"prompt_version": PROMPT_VERSION, "prompt_sha256": pin["versions"][PROMPT_VERSION]}
    bad = {**good, "prompt_sha256": "0" * 64}

    class Resp:
        def __init__(self, body):
            self.body = json.dumps(body).encode()

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(check_prompt_pin.urllib.request, "urlopen", lambda url, timeout: Resp(good))
    assert check_prompt_pin.url_problems(pin, "http://x/health") == []
    monkeypatch.setattr(check_prompt_pin.urllib.request, "urlopen", lambda url, timeout: Resp(bad))
    assert check_prompt_pin.url_problems(pin, "http://x/health")


def test_expect_config_catches_a_stale_deploy_without_the_canary():
    config = {"prompt_version": "1.2.0", "candidate": {"prompt_version": "1.3.0-candidate", "traffic_pct": 10}}
    stale = {"prompt_version": "1.2.0", "candidate": None}
    current = {"prompt_version": "1.2.0", "candidate": {"prompt_version": "1.3.0-candidate", "traffic_pct": 10}}
    assert check_prompt_pin.config_problems(stale, config)
    assert check_prompt_pin.config_problems(current, config) == []
    rolled_back = {**current, "prompt_version": "1.1.0"}
    assert check_prompt_pin.config_problems(rolled_back, config)
