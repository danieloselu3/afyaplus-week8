# ab_prompt_flag.py - sticky A/B assignment of a prompt variant to a partner key.
#
# The key is the county (normalised): a whole county sees one prompt, so clinicians in one
# place get consistent advice and results can be compared county by county. sha256, never
# the builtin hash(): Python salts str hashes per process, so cohorts would reshuffle on
# every restart and an hour-old trace could not say who was on the candidate.
import hashlib

import prompt_app


def bucket(key: str) -> int:
    """0-99, the same on every machine and in every process."""
    return int(hashlib.sha256(key.strip().lower().encode("utf-8")).hexdigest(), 16) % 100


def assign_variant(key: str, pct_b: int) -> str:
    """'B' for buckets 0..pct_b-1, else 'A'. So 10 means ten percent, never eleven."""
    return "B" if bucket(key) < pct_b else "A"


def select_prompt(key: str) -> tuple[str, str, str, str]:
    """(variant, prompt_version, prompt_text, prompt_sha256) for this partner key."""
    variant = assign_variant(key, prompt_app.CANDIDATE_PCT) if prompt_app.CANDIDATE_VERSION else "A"
    version, text, sha = prompt_app.prompt_for(variant)
    return variant, version, text, sha


if __name__ == "__main__":
    # Stickiness AND split: Migori twice (same answer both times), Kisumu as a known A.
    for key in ["Migori", "Migori", "Kisumu"]:
        variant, version, _text, sha = select_prompt(key)
        print(f"{key:8} bucket {bucket(key):2} -> {variant} prompt {version} ({sha[:12]})")
