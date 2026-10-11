# ab_metrics.py - one JSONL row per /triage request, so A and B can be compared offline.
# It holds no patient text: the message is reduced to a short hash (repeat detection only).
import hashlib
import json
import threading

from config import LOG_DIR

LOG = LOG_DIR / "ab_requests.jsonl"
_lock = threading.Lock()


def record(*, trace_id: str, county: str, variant: str, prompt_version: str, urgency: str,
           cache: str, latency_ms: float, tokens_in: int, tokens_out: int, message: str) -> dict:
    row = {"trace": trace_id, "county": county.strip().lower(), "variant": variant,
           "prompt_version": prompt_version, "urgency": urgency, "cache": cache,
           "latency_ms": round(latency_ms, 1), "tokens_in": tokens_in, "tokens_out": tokens_out,
           "message_hash": hashlib.sha256(" ".join(message.lower().split()).encode()).hexdigest()[:10]}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with _lock, LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row
