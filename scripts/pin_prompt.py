"""Pin a NEW prompt file in prompts/pin.json (refuses to re-pin a version that already has one).

    python scripts/pin_prompt.py 1.3.0-candidate

Re-pinning an existing version would be editing a pinned prompt in place, which the whole
week forbids: write a new version file instead. The one exception is a draft that has
never left its pull request, and that needs --replace-unreleased, so the diff shows it.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--replace-unreleased", action="store_true",
                    help="re-pin a draft that was never merged to main or tagged")
    args = ap.parse_args()
    # Standalone on purpose: importing prompt_app would fail closed on the very mismatch
    # this tool exists to resolve. Same bytes, same hash rule as prompt_app.load_pinned.
    path = ROOT / "prompts" / f"triage_system_v{args.version}.txt"
    if not path.is_file():
        print(f"no prompt file {path.name}")
        return 1
    pin_file = ROOT / "prompts" / "pin.json"
    pin = json.loads(pin_file.read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    old = pin["versions"].get(args.version)
    if old and old != digest and not args.replace_unreleased:
        print(f"REFUSED: {args.version} is already pinned to {old[:12]}. Add a new version file.")
        return 1
    pin["versions"][args.version] = digest
    pin_file.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(f"pinned {args.version} = {digest}" + (f" (replaced unreleased {old[:12]})" if old and old != digest else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
