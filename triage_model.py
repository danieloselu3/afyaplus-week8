# triage_model.py - the AI model behind /triage.
# Real path: gpt-4o-mini returning JSON we validate like any other input.
# Stub path: the course's keyword model, same shape, no cost (tests and fallback).
import os
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from config import LLM_BASE_URL, OPENAI_MODEL, TRIAGE_BACKEND

# Safety floor: these words always mean "high", whatever the model says.
URGENT_WORDS = ["chest pain", "bleeding", "unconscious", "cannot breathe",
                "can't breathe", "seizure", "convulsion", "not breathing"]

SYSTEM_PROMPT = (
    "You are a triage assistant for AfyaPlus, a Kenyan community health network. "
    "Classify the urgency of the patient's message and give ONE short, safe, "
    "non-diagnostic next step (max 2 sentences). Never prescribe medicines or doses. "
    "urgency must be one of: low (self-care, monitor), medium (see a clinician within "
    "24 hours), high (go to a clinic or emergency care now). "
    'Reply only with JSON: {"urgency": "...", "advice": "..."}'
)


class ModelUnavailable(Exception):
    """The model could not produce a usable answer; the API turns this into a 503."""


class TriageResult(BaseModel):
    """What we accept back from the model: a response is just another door."""
    urgency: Literal["low", "medium", "high"]
    advice: str = Field(min_length=5, max_length=400)


def _red_flag(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in URGENT_WORDS)


# Load tests only: make the free stub as slow as a real model call (measured p50 ~1,000 ms).
STUB_LATENCY_MS = int(os.getenv("STUB_LATENCY_MS", "0"))


def _stub(message: str) -> TriageResult:
    if STUB_LATENCY_MS:
        time.sleep(STUB_LATENCY_MS / 1000)
    if _red_flag(message):
        return TriageResult(urgency="high", advice="Please go to the nearest clinic now.")
    return TriageResult(urgency="low", advice="Rest, drink fluids, and monitor your symptoms.")


_client = None


def _openai(message: str, county: str) -> tuple[TriageResult, dict]:
    global _client
    from openai import OpenAI            # imported lazily so the stub path needs no key
    if _client is None:
        # max_retries=1: a sane client, never a retry storm (see cost/retry_storm.py)
        _client = OpenAI(api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
                         base_url=LLM_BASE_URL, timeout=20, max_retries=1)
    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        max_tokens=150,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": f"County: {county}\nMessage: {message}"}],
    )
    result = TriageResult.model_validate_json(response.choices[0].message.content)
    usage = {"tokens_in": response.usage.prompt_tokens,
             "tokens_out": response.usage.completion_tokens}
    return result, usage


def triage_model(message: str, county: str) -> dict:
    """Return {"urgency", "advice", "model_used", "tokens_in", "tokens_out"}.
    Raises ModelUnavailable on any upstream failure or malformed model output."""
    if TRIAGE_BACKEND == "stub":
        result, usage, model_used = _stub(message), {"tokens_in": 0, "tokens_out": 0}, "triage-stub-v1"
    else:
        try:
            result, usage = _openai(message, county)
        except ValidationError as exc:
            raise ModelUnavailable("model returned malformed output") from exc
        except Exception as exc:          # network, auth, rate limit, timeout
            raise ModelUnavailable(type(exc).__name__) from exc
        model_used = OPENAI_MODEL
    urgency = result.urgency
    if _red_flag(message) and urgency != "high":
        urgency = "high"                  # the model may never downgrade a red flag
        result.advice = "Warning signs reported: go to the nearest clinic now. " + result.advice
    return {"urgency": urgency, "advice": result.advice, "model_used": model_used, **usage}
