"""Move the lockstep release to a new version in every place check_release.py checks.

    python scripts/bump_release.py 1.3.1

Edits: config/triage.yaml release, prompts/pin.json bundle_version, and the afyaplus image
tags, IMAGE_TAG build args and afyaplus.version labels in both compose files. It does NOT
write the CHANGELOG entry (a human says what changed) and does not tag: the tag is pushed
after the pull request merges. Run scripts/check_release.py afterwards.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def main() -> int:
    if len(sys.argv) != 2 or not SEMVER.match(sys.argv[1]):
        print("usage: python scripts/bump_release.py <semver>")
        return 2
    new = sys.argv[1]
    cfg = ROOT / "config" / "triage.yaml"
    text = cfg.read_text(encoding="utf-8")
    old = re.search(r'^release: "([^"]+)"', text, flags=re.M).group(1)
    cfg.write_text(text.replace(f'release: "{old}"', f'release: "{new}"', 1), encoding="utf-8")

    pin_file = ROOT / "prompts" / "pin.json"
    pin = json.loads(pin_file.read_text(encoding="utf-8"))
    pin["bundle_version"] = new
    pin_file.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")

    for rel in ("docker-compose.yml", "deploy/docker-compose.cost.yml"):
        f = ROOT / rel
        s = f.read_text(encoding="utf-8")
        s = re.sub(rf"(afyaplus-(?:triage|agent):){re.escape(old)}\b", rf"\g<1>{new}", s)
        s = s.replace(f'IMAGE_TAG: "{old}"', f'IMAGE_TAG: "{new}"')
        s = s.replace(f'afyaplus.version: "{old}"', f'afyaplus.version: "{new}"')
        f.write_text(s, encoding="utf-8")
    print(f"release {old} -> {new}: config, prompt bundle, compose tags/args/labels. "
          f"Now add '## [{new}]' to CHANGELOG.md and run scripts/check_release.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
