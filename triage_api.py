# triage_api.py - the secured AfyaPlus triage service
from typing import Literal
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from auth import auth_router, require_role
import prompt_app
import response_cache
from config import (CACHE_ENABLED, LLM_BASE_URL, OPENAI_MODEL, TRIAGE_BACKEND,
                    TRIAGE_RATE_LIMIT_PER_MIN, VERSION, get_logger)
from observability import add_request_logging
from rate_limit import check_rate_limit
from triage_model import ModelUnavailable, triage_model

SERVICE = "triage-api"
log = get_logger("triage_api", "triage_api.log")
audit = get_logger("audit", "audit.log")

app = FastAPI(title="AfyaPlus Triage API", version=VERSION)
add_request_logging(app, log)
app.include_router(auth_router)          # POST /token, shared with the agent API


# ---------- the agreement: typed request and response models ----------

class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    patient_message: str = Field(min_length=5, max_length=1000,
                                 examples=["I have chest pain and feel dizzy"])
    county: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z][A-Za-z '\-]+$",
                        examples=["Kisumu"])


class TriageResponse(BaseModel):
    urgency: Literal["low", "medium", "high"]
    advice: str
    model_used: str
    prompt_version: str      # which pinned prompt answered: A/B attribution without log scraping
    handled_for: str
    request_id: str


class HealthResponse(BaseModel):
    service: str
    version: str
    status: Literal["ok"]
    model_backend: str
    model: str
    llm_endpoint: str        # host only: proves the endpoint switch without leaking keys
    cache: str               # redis | memory | off
    prompt_version: str      # variant A, as loaded and hashed at startup
    prompt_sha256: str
    candidate: dict | None   # variant B (version, sha256, traffic_pct) when a canary runs
    config_sha256: str       # hash of config/triage.yaml as loaded
    model_version: str
    image_tag: str           # set at build time (Dockerfile ARG IMAGE_TAG)
    git_sha: str


def write_audit_line(trace_id: str, username: str, county: str, urgency: str) -> None:
    """Who asked, when, where, and what came back. Never the message text."""
    audit.info("trace=%s user=%s county=%s urgency=%s", trace_id, username, county, urgency)


# ---------- endpoints ----------

@app.get("/health", response_model=HealthResponse)
def health():
    """Unprotected liveness probe for load balancers and Kubernetes."""
    return {"service": SERVICE, "version": VERSION, "status": "ok", "model_backend": TRIAGE_BACKEND,
            "model": OPENAI_MODEL,
            "llm_endpoint": urlparse(LLM_BASE_URL).netloc if LLM_BASE_URL else "api.openai.com",
            "cache": response_cache.backend() if CACHE_ENABLED else "off",
            **prompt_app.version_info()}


@app.post("/triage", response_model=TriageResponse,
          responses={401: {"description": "Missing, invalid or expired token"},
                     403: {"description": "Authenticated, but role is not coordinator"},
                     429: {"description": "Over TRIAGE_RATE_LIMIT_PER_MIN calls a minute"},
                     503: {"description": "The AI model is unavailable"}})
def triage(body: TriageRequest, request: Request, response: Response, background: BackgroundTasks,
           user: dict = Depends(require_role("coordinator"))):
    check_rate_limit(f"triage:{user['sub']}", max_requests=TRIAGE_RATE_LIMIT_PER_MIN)
    trace_id = request.state.trace_id
    try:
        result, cache_status = response_cache.cached_triage(
            triage_model, body.patient_message, body.county)
    except ModelUnavailable as exc:
        log.error("trace=%s model_error=%s", trace_id, exc)
        raise HTTPException(status_code=503, detail="The AI model is unavailable. Try again shortly.")
    billed = cache_status != "HIT"       # a HIT costs no tokens: that is the whole lever
    log.info("trace=%s model=%s cache=%s tokens_in=%s tokens_out=%s",
             trace_id, result["model_used"], cache_status,
             result["tokens_in"] if billed else 0, result["tokens_out"] if billed else 0)
    response.headers["X-Cache"] = cache_status
    background.add_task(write_audit_line, trace_id, user["sub"], body.county, result["urgency"])
    return TriageResponse(urgency=result["urgency"], advice=result["advice"],
                          model_used=result["model_used"], prompt_version=result["prompt_version"],
                          handled_for=user["sub"],
                          request_id=trace_id)
