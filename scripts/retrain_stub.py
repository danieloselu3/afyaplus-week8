"""Retrain STUB: we have no GPU for this service, so no weights are trained here.

    python scripts/retrain_stub.py --reason "monthly refresh"     # edits config + CHANGELOG

What a real retrain job would change, and this stub changes honestly:
  - config/triage.yaml model_version: base-2024-07-18 -> retrain-stub-<YYYYMMDD>-<n>
  - CHANGELOG.md: a line under [Unreleased] saying no weights were trained
What it deliberately does NOT change: `model` (still the same OpenAI snapshot). A real retrain
would change `model` to the new fine-tune's id, and then eval_prompts.py would fail closed
("answers were recorded on ... re-record") until the golden set is re-recorded on the new
model and reviewed. That is the gate a retrain has to pass, and it is already wired.
The edit lands as a pull request, so it goes through every gate like any other change.
"""
import argparse
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "triage.yaml"
CHANGELOG = ROOT / "CHANGELOG.md"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reason", default="scheduled retrain (stub)")
    args = ap.parse_args()
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r"^model_version: (\S+)", text, flags=re.M)
    old = match.group(1)
    today = date.today().strftime("%Y%m%d")
    n = 1 + sum(1 for _ in re.finditer(rf"retrain-stub-{today}-\d+", CHANGELOG.read_text(encoding="utf-8")))
    new = f"retrain-stub-{today}-{n}"
    CONFIG.write_text(text.replace(f"model_version: {old}", f"model_version: {new}", 1), encoding="utf-8")

    log = CHANGELOG.read_text(encoding="utf-8")
    line = (f"- **Retrain stub** ({date.today().isoformat()}, {args.reason}): model_version "
            f"`{old}` -> `{new}`. **No weights were trained**; `model` is unchanged.\n")
    marker = "## [Unreleased]\n"
    CHANGELOG.write_text(log.replace(marker, marker + "\n### Model\n" + line, 1), encoding="utf-8")
    print(f"model_version {old} -> {new} (stub: no weights trained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
