"""Release alignment gate: one version string, everywhere it appears.

    python scripts/check_release.py              # in CI on every run
    python scripts/check_release.py --tag v1.2.0 # also on a tag push (CI passes the tag)

The release is config/triage.yaml `release`. Fails (exit 1) unless ALL of these agree:
  prompts/pin.json bundle_version, the MCP server's MCP_VERSION, every afyaplus image tag
  and afyaplus.version label in the compose files, a CHANGELOG.md section for the release,
  and (when given) the git tag, which must be exactly v<release>.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
COMPOSE_FILES = ["docker-compose.yml", "deploy/docker-compose.cost.yml"]


def compose_versions(path: Path) -> list[tuple[str, str]]:
    """(where, version) for every afyaplus image tag and afyaplus.version label."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    found = []

    def walk(node, where):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "image" and isinstance(value, str) and value.startswith("afyaplus-"):
                    found.append((f"{where}.image", value.rsplit(":", 1)[-1]))
                elif key == "afyaplus.version":
                    found.append((f"{where}.label", str(value)))
                elif key == "IMAGE_TAG":
                    found.append((f"{where}.build-arg", str(value)))
                else:
                    walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{where}[{i}]")
    walk(doc, path.name)
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=os.getenv("GITHUB_REF_NAME") if os.getenv("GITHUB_REF_TYPE") == "tag" else None)
    args = ap.parse_args()

    release = str(yaml.safe_load((ROOT / "config" / "triage.yaml").read_text())["release"])
    checks = [("config/triage.yaml release", release)]
    checks.append(("prompts/pin.json bundle_version",
                   str(json.loads((ROOT / "prompts" / "pin.json").read_text())["bundle_version"])))
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("LOG_DIR", str(ROOT / "logs"))
    from logistics_mcp_versioned import MCP_VERSION
    checks.append(("logistics_mcp_versioned.MCP_VERSION", MCP_VERSION))
    for f in COMPOSE_FILES:
        checks += compose_versions(ROOT / f)
    if args.tag:
        checks.append(("git tag", args.tag[1:] if args.tag.startswith("v") else f"<no v prefix: {args.tag}>"))

    problems = [] if SEMVER.match(release) else [f"release {release!r} is not semver"]
    for where, value in checks:
        mark = "ok " if value == release else "BAD"
        print(f"  {mark} {where:52} {value}")
        if value != release:
            problems.append(f"{where} is {value}, release is {release}")
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists() or f"## [{release}]" not in changelog.read_text(encoding="utf-8"):
        problems.append(f"CHANGELOG.md has no '## [{release}]' section")
    if problems:
        print("RELEASE ALIGNMENT FAILED")
        for p in problems:
            print("  -", p)
        return 1
    print(f"release {release} aligned across {len(checks)} places + CHANGELOG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
