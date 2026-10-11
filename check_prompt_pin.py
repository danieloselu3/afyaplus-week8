"""CI gate: production never runs a prompt the git tree did not pin.

    python check_prompt_pin.py                                   # offline: files vs pins
    python check_prompt_pin.py --url http://127.0.0.1:8000/health   # running service vs pins

Offline it fails (exit 1) when a prompt file has no pin, a pin has no file, a pinned file's
bytes changed (edited in place), or the active/candidate versions in config/triage.yaml are
not pinned. With --url it fails when the running /health reports a version or hash that the
pin does not, or when /health is unreachable: a service that will not answer has not passed.
"""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT / "prompts"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def offline_problems(pin: dict, config: dict) -> list[str]:
    problems = []
    files = {p.name[len("triage_system_v"):-len(".txt")]: p
             for p in PROMPTS.glob("triage_system_v*.txt")}
    for version, path in sorted(files.items()):
        pinned = pin["versions"].get(version)
        if pinned is None:
            problems.append(f"{path.name} has no pin: add it to prompts/pin.json in the same PR")
        elif sha256_file(path) != pinned:
            problems.append(f"{path.name} changed after it was pinned "
                            f"({sha256_file(path)[:12]} != {pinned[:12]}): add a new version file instead")
    for version in pin["versions"]:
        if version not in files:
            problems.append(f"pin for {version} has no prompts/triage_system_v{version}.txt")
    wanted = [config["prompt_version"]]
    cand = config.get("candidate") or {}
    if cand.get("prompt_version") and cand.get("traffic_pct", 0) > 0:
        wanted.append(cand["prompt_version"])
    for version in wanted:
        if version not in pin["versions"]:
            problems.append(f"config serves prompt {version}, which is not pinned")
    if str(pin.get("bundle_version")) != str(config["release"]):
        problems.append(f"prompt bundle_version {pin.get('bundle_version')} != release {config['release']}")
    return problems


def url_problems(pin: dict, url: str) -> list[str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            health = json.loads(resp.read().decode())
    except Exception as exc:
        return [f"/health unreachable: {exc}"]
    problems = []
    served = [("A", health.get("prompt_version"), health.get("prompt_sha256"))]
    if health.get("candidate"):
        c = health["candidate"]
        served.append(("B", c.get("prompt_version"), c.get("prompt_sha256")))
    for variant, version, sha in served:
        expected = pin["versions"].get(version)
        if expected != sha:
            problems.append(f"variant {variant}: running {version} {str(sha)[:12]} but pin says "
                            f"{(expected or 'nothing')[:12]}")
        else:
            print(f"variant {variant}: prompt {version} sha256 {sha[:12]}... matches pin")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="a running /health to compare against the pin")
    args = ap.parse_args()
    pin = json.loads((PROMPTS / "pin.json").read_text(encoding="utf-8"))
    config = yaml.safe_load((ROOT / "config" / "triage.yaml").read_text(encoding="utf-8"))
    problems = url_problems(pin, args.url) if args.url else offline_problems(pin, config)
    if problems:
        print("PROMPT PIN CHECK FAILED")
        for p in problems:
            print("  -", p)
        return 1
    if not args.url:
        print(f"prompt pins OK: bundle {pin['bundle_version']}, "
              + ", ".join(f"{v}={s[:12]}..." for v, s in pin["versions"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
