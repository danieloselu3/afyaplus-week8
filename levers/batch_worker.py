"""Lever 2: a batch queue for triage work nobody is waiting on.

The case: SMS messages that arrive after clinic hours are read by a coordinator at
08:00, not answered live. They do not belong on the interactive /triage path. A
worker drains them in batches of N messages per model call, so the system prompt
is paid once per batch instead of once per message.

    python levers/batch_worker.py              # 3 sample jobs through the stub, then 0 (idempotent)

Queue: SQLite (the scored fallback; a Redis list is the production shape).
status pending -> done, or -> dead after MAX_ATTEMPTS failed tries (dead-letter).
Urgent messages never wait for this queue: the red-flag floor still applies per message,
and the interactive /triage path is unchanged.
"""
import json
import os
import sqlite3
from pathlib import Path
from typing import Literal

import _paths  # noqa: F401  (puts the repo root on sys.path)
import response_cache
from pydantic import BaseModel, Field
from triage_model import SYSTEM_PROMPT, _red_flag

COUNTY = "Nairobi"
DB =Path(os.getenv("BATCH_DB", Path(__file__).resolve().parent / "jobs.sqlite"))
MAX_ATTEMPTS = 3
SCHEMA = ("CREATE TABLE IF NOT EXISTS jobs ("
          "id INTEGER PRIMARY KEY AUTOINCREMENT,"
          "text TEXT NOT NULL,"
          "status TEXT NOT NULL DEFAULT 'pending',"
          "attempts INTEGER NOT NULL DEFAULT 0,"
          "result TEXT)")

# Same clinical rules as the live prompt; only the reply format changes.
BATCH_SYSTEM_PROMPT = SYSTEM_PROMPT.rsplit("Reply only", 1)[0] + (
    "You will receive a JSON list of messages, each with an id. Classify each one "
    "independently; never let one message influence another. Reply only with JSON: "
    '{"results": [{"id": <id>, "urgency": "...", "advice": "..."}]} with exactly one '
    "result per input id.")


class BatchItem(BaseModel):
    id: int
    urgency: Literal["low", "medium", "high"]
    advice: str = Field(min_length=5, max_length=400)


class BatchReply(BaseModel):
    results: list[BatchItem]


def init(db: Path = DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def enqueue(conn: sqlite3.Connection, text: str) -> None:
    conn.execute("INSERT INTO jobs(text) VALUES (?)", (text,))
    conn.commit()


def fetch_batch(conn: sqlite3.Connection, n: int = 8) -> list[tuple[int, str]]:
    return conn.execute("SELECT id, text FROM jobs WHERE status='pending' ORDER BY id LIMIT ?",
                        (n,)).fetchall()


def _stub_batch(items: list[tuple[int, str]]) -> tuple[list[dict], dict]:
    results = [{"id": i, "urgency": "high" if _red_flag(t) else "low",
                "advice": "Please go to the nearest clinic now." if _red_flag(t)
                else "Rest, drink fluids, and monitor your symptoms."} for i, t in items]
    return results, {"tokens_in": 0, "tokens_out": 0}


def _openai_batch(items: list[tuple[int, str]]) -> tuple[list[dict], dict]:
    from openai import OpenAI
    from config import LLM_BASE_URL, OPENAI_MODEL
    client = OpenAI(api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
                    base_url=LLM_BASE_URL, timeout=60, max_retries=1)
    payload = json.dumps([{"id": i, "message": t} for i, t in items])
    response = client.chat.completions.create(
        model=OPENAI_MODEL, temperature=0, max_tokens=80 * len(items) + 50,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": BATCH_SYSTEM_PROMPT},
                  {"role": "user", "content": f"County: Nairobi\nMessages: {payload}"}])
    reply = BatchReply.model_validate_json(response.choices[0].message.content)
    usage = {"tokens_in": response.usage.prompt_tokens, "tokens_out": response.usage.completion_tokens}
    return [r.model_dump() for r in reply.results], usage


def summarise_batch(items: list[tuple[int, str]]) -> tuple[list[dict], dict]:
    """One model call for the whole batch. Raises if any id is missing or extra,
    so a half-answered batch goes back to pending instead of being marked done."""
    backend = os.getenv("TRIAGE_BACKEND", "openai")
    results, usage = (_stub_batch if backend == "stub" else _openai_batch)(items)
    if sorted(r["id"] for r in results) != sorted(i for i, _ in items):
        raise ValueError("batch reply ids do not match the request ids")
    texts = dict(items)
    for r in results:                     # the model may never downgrade a red flag
        if _red_flag(texts[r["id"]]) and r["urgency"] != "high":
            r["urgency"] = "high"
            r["advice"] = "Warning signs reported: go to the nearest clinic now. " + r["advice"]
    return results, usage


def process_once(conn: sqlite3.Connection, batch_size: int = 8) -> dict:
    """Take one batch. Messages the live cache already answered today are done for free;
    the rest go to the model in ONE call. Attempts are counted BEFORE the work, so a job
    that crashes the worker still burns a try; after MAX_ATTEMPTS it is dead and a person
    looks at it."""
    batch = fetch_batch(conn, batch_size)
    if not batch:
        return {"done": 0, "failed": 0, "from_cache": 0, "model_calls": 0,
                "tokens_in": 0, "tokens_out": 0}
    ids = [i for i, _ in batch]
    marks = ",".join("?" * len(ids))
    conn.execute(f"UPDATE jobs SET attempts = attempts + 1 WHERE id IN ({marks})", ids)
    conn.commit()
    cached = {}
    for i, text in batch:
        hit = response_cache.lookup(text, COUNTY)
        if hit is not None:
            cached[i] = {"id": i, "urgency": hit["urgency"], "advice": hit["advice"], "source": "cache"}
    to_model = [(i, t) for i, t in batch if i not in cached]
    usage = {"tokens_in": 0, "tokens_out": 0}
    results = []
    if to_model:
        try:
            results, usage = summarise_batch(to_model)
        except Exception as exc:
            conn.execute(f"UPDATE jobs SET status='dead' WHERE id IN ({marks}) AND attempts >= ?",
                         ids + [MAX_ATTEMPTS])
            conn.commit()
            print(f"batch of {len(ids)} failed ({type(exc).__name__}: {exc}); rows stay pending")
            return {"done": 0, "failed": len(ids), "from_cache": 0, "model_calls": 1,
                    "tokens_in": 0, "tokens_out": 0}
    for r in results + list(cached.values()):
        conn.execute("UPDATE jobs SET status='done', result=? WHERE id=?", (json.dumps(r), r["id"]))
    conn.commit()
    return {"done": len(results) + len(cached), "failed": 0, "from_cache": len(cached),
            "model_calls": 1 if to_model else 0, **usage}


def counts(conn: sqlite3.Connection) -> dict:
    return dict(conn.execute("SELECT status, count(*) FROM jobs GROUP BY status").fetchall())


if __name__ == "__main__":
    os.environ["TRIAGE_BACKEND"] = "stub"   # the idempotency demo is free; batch_measure.py goes live
    conn = init()
    for sample in ["Fever for two days, drinking fluids", "Chest pain radiating to left arm",
                   "Runny nose and sneezing"]:
        enqueue(conn, sample)
    print("processed", process_once(conn)["done"])
    print("processed", process_once(conn)["done"])
    print(counts(conn))
