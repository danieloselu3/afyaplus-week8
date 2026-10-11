"""Record live model answers for the golden set, once per prompt version, for CI to replay.

    python scripts/record_responses.py --version 1.2.0          # live gpt-4o-mini (~30 calls)
    python scripts/record_responses.py --version 1.2.0 --stub   # free, for wiring checks only

Writes fixtures/responses/<prompt_sha256>.json. The fixture is keyed on the prompt's
CONTENT hash, not its version string, so an edited prompt has no recorded answers and the
eval gate fails closed until somebody records (and reviews) new ones. The fixture also
records the model and a hash of the golden set: if either changes, the gate refuses to
reuse old answers.

Answers go through triage_model() itself, so the red-flag safety floor is applied exactly as
in production. The eval scores what a patient would actually receive.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "evals" / "golden.jsonl"
OUT_DIR = ROOT / "fixtures" / "responses"


def golden_sha() -> str:
    return hashlib.sha256(GOLDEN.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="bare semver of a pinned prompt, e.g. 1.2.0")
    ap.add_argument("--stub", action="store_true", help="record the free stub model (never commit)")
    args = ap.parse_args()
    os.environ["TRIAGE_BACKEND"] = "stub" if args.stub else "openai"
    os.environ["CACHE_ENABLED"] = "false"
    sys.path.insert(0, str(ROOT))
    import prompt_app                              # noqa: E402  (env must be set first)
    from config import OPENAI_MODEL, TRIAGE_BACKEND  # noqa: E402
    from triage_model import triage_model          # noqa: E402

    text, sha = prompt_app.load_pinned(args.version)          # only pinned prompts are recorded
    cases = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id, tokens = {}, 0
    for case in cases:
        out = triage_model(case["message"], case["county"], prompt=(args.version, text))
        by_id[case["id"]] = {"urgency": out["urgency"], "advice": out["advice"],
                             "tokens_in": out["tokens_in"], "tokens_out": out["tokens_out"]}
        tokens += out["tokens_in"] + out["tokens_out"]
        print(f"{case['id']} expected={case['expected_urgency']} got={out['urgency']:6} {out['advice'][:70]}")
    fixture = {
        "prompt_version": args.version, "prompt_sha256": sha,
        "model": "triage-stub-v1" if TRIAGE_BACKEND == "stub" else OPENAI_MODEL,
        "temperature": prompt_app.CONFIG["temperature"],
        "golden_sha256": golden_sha(), "n": len(cases),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by_id": by_id,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"{sha}.json"
    out_file.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"recorded {len(cases)} answers for prompt {args.version} ({sha[:12]}) on {fixture['model']}, "
          f"{tokens} tokens -> {out_file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
