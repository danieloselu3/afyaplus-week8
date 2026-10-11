# response_cache.py - Week 7 lever 1: an exact-match response cache for /triage.
# Same message + county + model + prompt version = same answer, so we pay once.
# Redis when REDIS_URL answers (shared by every replica), else an in-process dict.
# A broken cache must never break triage: every cache error degrades to a MISS.
import hashlib
import json
import time

from config import CACHE_ENABLED, CACHE_TTL_S, OPENAI_MODEL, REDIS_URL, TRIAGE_BACKEND, get_logger
from triage_model import SYSTEM_PROMPT

log = get_logger("response_cache", "triage_api.log")

# Changing the system prompt changes this tag, so stale answers from an old prompt are never served.
PROMPT_TAG = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]

metrics = {"hits": 0, "misses": 0}
_mem: dict[str, tuple[float, dict]] = {}
_redis = None
_backend: str | None = None


def backend() -> str:
    """'redis' if REDIS_URL answers a ping, else 'memory'. Decided once, on first use."""
    global _backend, _redis
    if _backend is None:
        _backend = "memory"
        if REDIS_URL:
            try:
                import redis
                client = redis.Redis.from_url(REDIS_URL, decode_responses=True,
                                              socket_timeout=0.5, socket_connect_timeout=0.5)
                client.ping()
                _redis, _backend = client, "redis"
            except Exception as exc:
                log.warning("cache: redis unavailable (%s), using in-memory dict", type(exc).__name__)
        log.info("cache: backend=%s ttl_s=%s", _backend, CACHE_TTL_S)
    return _backend


def normalise(message: str) -> str:
    """Case and all whitespace runs collapse, so 'Fever  2 days ' == 'fever 2 days'."""
    return " ".join(message.lower().split())


def make_key(message: str, county: str) -> str:
    model = OPENAI_MODEL if TRIAGE_BACKEND != "stub" else "stub"
    raw = f"{model}|{PROMPT_TAG}|{normalise(county)}|{normalise(message)}"
    return "triage:" + hashlib.sha256(raw.encode()).hexdigest()


def _get(key: str) -> dict | None:
    try:
        if backend() == "redis":
            raw = _redis.get(key)
            return json.loads(raw) if raw else None
        row = _mem.get(key)
        if row and row[0] > time.time():
            return row[1]
        _mem.pop(key, None)
        return None
    except Exception as exc:
        log.warning("cache: get failed (%s), treating as miss", type(exc).__name__)
        return None


def _set(key: str, value: dict) -> None:
    try:
        if backend() == "redis":
            _redis.setex(key, CACHE_TTL_S, json.dumps(value))
        else:
            _mem[key] = (time.time() + CACHE_TTL_S, value)
    except Exception as exc:
        log.warning("cache: set failed (%s), answer not cached", type(exc).__name__)


def cached_triage(model_fn, message: str, county: str) -> tuple[dict, str]:
    """Return (result, 'HIT' | 'MISS' | 'BYPASS'). Exceptions from model_fn propagate,
    so a failed model call is never cached."""
    if not CACHE_ENABLED:
        return model_fn(message, county), "BYPASS"
    key = make_key(message, county)
    hit = _get(key)
    if hit is not None:
        metrics["hits"] += 1
        return hit, "HIT"
    result = model_fn(message, county)
    _set(key, result)
    metrics["misses"] += 1
    return result, "MISS"


def lookup(message: str, county: str) -> dict | None:
    """Read-only peek for other paths (the overnight batch worker). Never writes, so
    answers produced elsewhere can never leak into what live /triage serves."""
    return _get(make_key(message, county)) if CACHE_ENABLED else None


def hit_rate() -> float:
    total = metrics["hits"] + metrics["misses"]
    return metrics["hits"] / total if total else 0.0


def reset() -> None:
    """Empty the in-process cache and counters (tests and measurement runs)."""
    _mem.clear()
    metrics.update(hits=0, misses=0)
    if _backend == "redis":
        for key in _redis.scan_iter("triage:*"):
            _redis.delete(key)
