from fastapi.testclient import TestClient

import response_cache
import triage_api
from triage_model import ModelUnavailable

client = TestClient(triage_api.app)
MSG = {"patient_message": "Fever for two days, drinking fluids", "county": "Kisumu"}


def login():
    r = client.post("/token", json={"username": "mercy", "password": "logistics2026"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_identical_message_is_miss_then_hit():
    headers = login()
    first = client.post("/triage", json=MSG, headers=headers)
    second = client.post("/triage", json=MSG, headers=headers)
    assert [first.headers["X-Cache"], second.headers["X-Cache"]] == ["MISS", "HIT"]
    assert first.json()["urgency"] == second.json()["urgency"]
    assert first.json()["advice"] == second.json()["advice"]
    assert response_cache.hit_rate() == 0.5


def test_case_and_whitespace_variants_share_a_key():
    a = response_cache.make_key("Fever for two days", "Kisumu")
    b = response_cache.make_key("  fever   FOR two days ", " kisumu")
    assert a == b


def test_different_county_or_message_is_a_different_key():
    base = response_cache.make_key("Fever for two days", "Kisumu")
    assert response_cache.make_key("Fever for two days", "Nakuru") != base
    assert response_cache.make_key("Fever for three days", "Kisumu") != base


def test_failed_model_call_is_never_cached(monkeypatch):
    headers = login()

    def down(message, county):
        raise ModelUnavailable("APITimeoutError")

    monkeypatch.setattr(triage_api, "triage_model", down)
    assert client.post("/triage", json=MSG, headers=headers).status_code == 503
    monkeypatch.undo()
    r = client.post("/triage", json=MSG, headers=headers)
    assert r.status_code == 200 and r.headers["X-Cache"] == "MISS"


def test_expired_entry_is_a_miss(monkeypatch):
    monkeypatch.setattr(response_cache, "CACHE_TTL_S", -1)   # every entry is born expired
    calls = []

    def model(message, county):
        calls.append(message)
        return {"urgency": "low", "advice": "Rest and drink fluids.", "model_used": "stub",
                "tokens_in": 0, "tokens_out": 0}

    assert response_cache.cached_triage(model, "cough", "Kisumu")[1] == "MISS"
    assert response_cache.cached_triage(model, "cough", "Kisumu")[1] == "MISS"
    assert len(calls) == 2


def test_cache_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(response_cache, "CACHE_ENABLED", False)
    headers = login()
    codes = [client.post("/triage", json=MSG, headers=headers).headers["X-Cache"] for _ in range(2)]
    assert codes == ["BYPASS", "BYPASS"]


def test_unreachable_redis_falls_back_to_memory(monkeypatch):
    monkeypatch.setattr(response_cache, "REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(response_cache, "_backend", None)
    assert response_cache.backend() == "memory"
