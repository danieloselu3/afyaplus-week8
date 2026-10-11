# prompt_app.py - the versioned prompt and run config: what the model is sent, and what
# /health (served by triage_api.py) reports about it.
#
# Convention (Week 8): PROMPT_VERSION holds a bare semver ("1.2.0"); the letter v lives
# only in the filename (prompts/triage_system_v1.2.0.txt). A pinned file is never edited
# in place: a change is a new file, a new pin and a new release.
import hashlib
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = ROOT / "prompts"
PIN_FILE = PROMPTS_DIR / "pin.json"
CONFIG_FILE = ROOT / "config" / "triage.yaml"


class PromptPinError(RuntimeError):
    """The prompt file on disk is not the one prompts/pin.json promised: refuse to serve."""


def load_config() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))


def load_prompt(version: str) -> str:
    """The exact text sent to the model as the system message. Fails fast, never falls back."""
    path = PROMPTS_DIR / f"triage_system_v{version}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"No prompt for version {version!r}: {path}")
    return path.read_text(encoding="utf-8")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_pin() -> dict:
    return json.loads(PIN_FILE.read_text(encoding="utf-8"))


def load_pinned(version: str) -> tuple[str, str]:
    """(text, sha256) for a version, only if the bytes match the committed pin."""
    text = load_prompt(version)
    digest = sha256(text)
    pinned = load_pin()["versions"].get(version)
    if pinned != digest:
        raise PromptPinError(f"prompt {version} sha256 {digest[:12]} does not match pin "
                             f"{(pinned or 'missing')[:12]}: re-pin through a pull request")
    return text, digest


CONFIG = load_config()
CONFIG_SHA256 = sha256(CONFIG_FILE.read_text(encoding="utf-8"))

# Variant A. PROMPT_VERSION overrides the config: rollback is "set PROMPT_VERSION=1.2.0",
# same image, no rebuild. Loaded and hashed ONCE at import, so /health describes the
# bytes this process holds, not whatever is on disk later.
PROMPT_VERSION = os.getenv("PROMPT_VERSION") or CONFIG["prompt_version"]
SYSTEM_PROMPT, PROMPT_SHA256 = load_pinned(PROMPT_VERSION)

# Variant B, the canary. Off unless a version is named AND the slice is above 0%.
_cand = CONFIG.get("candidate") or {}
CANDIDATE_VERSION = os.getenv("PROMPT_B_VERSION", _cand.get("prompt_version") or "") or None
CANDIDATE_PCT = int(os.getenv("PROMPT_B_PCT", _cand.get("traffic_pct") or 0))
if CANDIDATE_VERSION and CANDIDATE_PCT > 0:
    CANDIDATE_PROMPT, CANDIDATE_SHA256 = load_pinned(CANDIDATE_VERSION)
else:
    CANDIDATE_VERSION, CANDIDATE_PCT, CANDIDATE_PROMPT, CANDIDATE_SHA256 = None, 0, None, None


def prompt_for(variant: str) -> tuple[str, str, str]:
    """(version, text, sha256) for variant 'A' or 'B'."""
    if variant == "B" and CANDIDATE_VERSION:
        return CANDIDATE_VERSION, CANDIDATE_PROMPT, CANDIDATE_SHA256
    return PROMPT_VERSION, SYSTEM_PROMPT, PROMPT_SHA256


def version_info() -> dict:
    """Everything /health needs to prove what is running."""
    return {
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": PROMPT_SHA256,
        "candidate": ({"prompt_version": CANDIDATE_VERSION, "prompt_sha256": CANDIDATE_SHA256,
                       "traffic_pct": CANDIDATE_PCT} if CANDIDATE_VERSION else None),
        "config_sha256": CONFIG_SHA256,
        "model_version": CONFIG["model_version"],
        "image_tag": os.getenv("IMAGE_TAG", "dev"),
        "git_sha": os.getenv("GIT_SHA", "dev"),
    }


if __name__ == "__main__":
    # Pin material for prompts/pin.json
    print("PROMPT_VERSION", PROMPT_VERSION)
    print("PROMPT_SHA256", PROMPT_SHA256)
