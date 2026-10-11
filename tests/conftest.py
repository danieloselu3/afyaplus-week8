import os
import sys
import tempfile
from pathlib import Path

# Free, deterministic runs: stub model, throwaway logs, known secret, in-process cache.
# Set before any import.
os.environ["TRIAGE_BACKEND"] = "stub"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="afyaplus-test-logs-")
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["REDIS_URL"] = ""
ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT, ROOT / "levers", ROOT / "cost", ROOT / "deploy", ROOT / "scripts"):
    sys.path.insert(0, str(path))

import pytest  # noqa: E402

import rate_limit  # noqa: E402
import response_cache  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_state():
    """One test's rate-limit counters or cached answer must not leak into the next."""
    rate_limit.reset()
    response_cache.reset()
    yield
    rate_limit.reset()
    response_cache.reset()
