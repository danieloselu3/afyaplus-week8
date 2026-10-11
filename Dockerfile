# Dockerfile - AfyaPlus triage service
# Build: docker build -t afyaplus-triage:<version> .     (version = git tag without the v)
# Run:   docker run --rm -p 8000:8000 --env-file .env afyaplus-triage:<version>

# Small official base: Debian slim, no compilers or docs
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1. Dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2. An unprivileged user and a writable log directory (rarely changes, stays cached)
RUN useradd --create-home --uid 10001 afya && mkdir -p /app/logs && chown afya /app/logs

# 3. Code last: editing Python only rebuilds from here down
COPY config/ config/
COPY prompts/ prompts/
COPY config.py auth.py rate_limit.py observability.py prompt_app.py ab_prompt_flag.py ab_metrics.py triage_model.py response_cache.py triage_api.py ./

USER afya

# No secrets here. APP_ENV=production makes the service refuse to start
# unless JWT_SECRET is injected at runtime with --env-file / env_file.
ENV APP_ENV=production \
    LOG_DIR=/app/logs

# Build identity, reported on /health. CI passes the release and the commit:
#   docker build --build-arg IMAGE_TAG=1.2.0 --build-arg GIT_SHA=$(git rev-parse --short HEAD) .
ARG IMAGE_TAG=dev
ARG GIT_SHA=dev
ENV IMAGE_TAG=$IMAGE_TAG \
    GIT_SHA=$GIT_SHA

# FinOps labels travel with the image; deploy/docker-compose.cost.yml repeats them per container.
LABEL afyaplus.service="triage-api" \
      afyaplus.version="$IMAGE_TAG" \
      afyaplus.cost-center="clinical-ai" \
      org.opencontainers.image.revision="$GIT_SHA" \
      org.opencontainers.image.source="https://github.com/danieloselu3/afyaplus-week8"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "triage_api:app", "--host", "0.0.0.0", "--port", "8000"]
