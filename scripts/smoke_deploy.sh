#!/usr/bin/env bash
# smoke_deploy.sh - the deploy stub both deploy jobs run (and you can run locally).
# Starts the already-built image afyaplus-triage:$WANT_VERSION with Redis on the stub model,
# then proves the running service is exactly the pinned prompt, release and commit.
#   WANT_VERSION=1.3.0 WANT_SHA=<short sha> bash scripts/smoke_deploy.sh
set -euo pipefail
: "${WANT_VERSION:?set WANT_VERSION}" "${WANT_SHA:?set WANT_SHA}"
export TRIAGE_BACKEND=stub
[ -f .env ] || cp .env.example .env
COMPOSE="docker compose -f deploy/docker-compose.cost.yml"
trap '$COMPOSE logs --no-color triage-api | tail -20; $COMPOSE down' EXIT
$COMPOSE up -d --no-build --wait
curl -sf localhost:8000/health | tee health.json; echo
python check_prompt_pin.py --url http://127.0.0.1:8000/health --expect-config
python - <<'PY'
import json, os
h = json.load(open("health.json"))
assert h["version"] == os.environ["WANT_VERSION"] == h["image_tag"], h
assert h["git_sha"] == os.environ["WANT_SHA"], h
print(f"running image is release {h['image_tag']} at commit {h['git_sha']}, prompt {h['prompt_version']}")
PY
