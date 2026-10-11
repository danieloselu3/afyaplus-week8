import pytest

import batch_worker
import cost_model
import response_cache
from _paths import percentile


# ---------- lever 2: batch queue ----------

@pytest.fixture
def conn(tmp_path):
    return batch_worker.init(tmp_path / "jobs.sqlite")


def test_batch_drains_then_is_idempotent(conn):
    for text in ["Fever for two days", "Chest pain radiating to left arm", "Runny nose"]:
        batch_worker.enqueue(conn, text)
    first = batch_worker.process_once(conn, batch_size=8)
    second = batch_worker.process_once(conn, batch_size=8)
    assert first["done"] == 3 and first["model_calls"] == 1
    assert second["done"] == 0 and second["model_calls"] == 0
    assert batch_worker.counts(conn) == {"done": 3}


def test_poison_batch_goes_dead_after_three_attempts(conn, monkeypatch):
    def boom(items):
        raise ValueError("cannot summarise")
    monkeypatch.setattr(batch_worker, "summarise_batch", boom)
    batch_worker.enqueue(conn, "Persistent cough for a week")
    for _ in range(3):
        assert batch_worker.process_once(conn)["failed"] == 1
    assert batch_worker.counts(conn) == {"dead": 1}
    assert conn.execute("SELECT attempts FROM jobs").fetchone()[0] == 3


def test_reply_with_missing_id_is_rejected(monkeypatch):
    monkeypatch.setattr(batch_worker, "_stub_batch",
                        lambda items: ([{"id": 1, "urgency": "low", "advice": "Rest well."}],
                                       {"tokens_in": 0, "tokens_out": 0}))
    with pytest.raises(ValueError):
        batch_worker.summarise_batch([(1, "cough"), (2, "rash")])


def test_batch_never_downgrades_a_red_flag(monkeypatch):
    monkeypatch.setattr(batch_worker, "_stub_batch",
                        lambda items: ([{"id": i, "urgency": "low", "advice": "Rest well."}
                                        for i, _ in items], {"tokens_in": 0, "tokens_out": 0}))
    results, _ = batch_worker.summarise_batch([(1, "chest pain since morning")])
    assert results[0]["urgency"] == "high"


def test_worker_reads_the_live_cache_but_never_writes_it(conn):
    cached_text, new_text = "Sore throat, no fever", "Toothache for three days"
    response_cache.cached_triage(
        lambda m, c: {"urgency": "low", "advice": "Warm salt-water gargles.", "model_used": "stub",
                      "tokens_in": 0, "tokens_out": 0},
        cached_text, batch_worker.COUNTY)
    batch_worker.enqueue(conn, cached_text)
    batch_worker.enqueue(conn, new_text)
    out = batch_worker.process_once(conn)
    assert out["done"] == 2 and out["from_cache"] == 1 and out["model_calls"] == 1
    assert response_cache.lookup(new_text, batch_worker.COUNTY) is None


# ---------- cost arithmetic ----------

def test_api_usd_matches_the_course_reference():
    # Week 7 Monday Lesson 3: 450 prompt + 180 completion = $0.0001755
    assert cost_model.api_usd(450, 180) == pytest.approx(0.0001755)


def test_cache_hit_rate_scales_the_token_bill():
    shape = {"prompt": 100, "completion": 50}
    full = cost_model.token_usd_month(10_000, shape)
    assert cost_model.token_usd_month(10_000, shape, hit_rate=0.6) == pytest.approx(0.4 * full)


def test_batch_saving_applies_only_to_after_hours_share():
    shape = {"prompt": 100, "completion": 50}
    full = cost_model.token_usd_month(10_000, shape)
    with_batch = cost_model.token_usd_month(10_000, shape, batch_saving=0.5)
    assert with_batch == pytest.approx(full * (1 - cost_model.AFTER_HOURS_SHARE * 0.5))


def test_redis_break_even_is_where_saving_equals_redis_cost():
    levers = {"hit_rate_shared": 0.6, "hit_rate_2_separate": 0.36}
    n = cost_model.redis_break_even(levers)
    shape = cost_model.token_shape()
    saving = n * cost_model.api_usd(shape["prompt"], shape["completion"]) * 0.24
    assert saving == pytest.approx(cost_model.redis_usd_month(), rel=1e-4)


def test_container_cost_never_negative_inside_free_grant():
    assert cost_model.container_usd_month(1_000, replicas=0) == 0.0


def test_percentile_is_nearest_rank():
    values = list(range(1, 101))
    assert percentile(values, 50) == 50 and percentile(values, 95) == 95
    assert percentile([7.0], 95) == 7.0
