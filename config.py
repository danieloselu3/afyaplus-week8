# config.py - one place for version, settings and log setup
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# Single source of truth: config/triage.yaml `release`. /health, the git tag, the image tag,
# the prompt bundle and the MCP server version all use it (scripts/check_release.py).
_RUN_CONFIG = yaml.safe_load((Path(__file__).parent / "config" / "triage.yaml").read_text(encoding="utf-8"))
VERSION = str(_RUN_CONFIG["release"])

APP_ENV = os.getenv("APP_ENV", "development")
TRIAGE_BACKEND = os.getenv("TRIAGE_BACKEND", "openai")   # openai | stub

# Endpoint switch (Week 7 Tuesday): any OpenAI-compatible base URL, chosen by config,
# never by a code change. Unset = api.openai.com.
OPENAI_MODEL = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or _RUN_CONFIG["model"]
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None

# Lever 1: response cache. REDIS_URL unset or unreachable = in-process dict.
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
CACHE_TTL_S = int(os.getenv("CACHE_TTL_S", "600"))       # triage advice must expire
REDIS_URL = os.getenv("REDIS_URL", "")

# Per-coordinator ceiling on /triage calls a minute (Week 6 default: 5).
TRIAGE_RATE_LIMIT_PER_MIN = int(os.getenv("TRIAGE_RATE_LIMIT_PER_MIN", "5"))

LOG_DIR = Path(os.getenv("LOG_DIR", Path(__file__).parent / "logs"))

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def get_logger(name: str, filename: str) -> logging.Logger:
    """A logger that writes to logs/<filename> and to stderr (never stdout:
    the MCP server's stdout is the protocol channel)."""
    log = logging.getLogger(name)
    if log.handlers:
        return log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FORMAT)
    for handler in (logging.FileHandler(LOG_DIR / filename, encoding="utf-8"),
                    logging.StreamHandler()):
        handler.setFormatter(formatter)
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log
