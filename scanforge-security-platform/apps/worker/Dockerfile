FROM python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WORKER_CONCURRENCY=1 WORKER_WORKSPACE_ROOT=/var/lib/scanforge/workspaces
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/worker/pyproject.toml .
RUN pip install --no-cache-dir .
COPY apps/worker/app ./app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin worker \
    && install -d -m 0700 -o 10001 -g 10001 /var/lib/scanforge/workspaces
USER 10001:10001
CMD ["python", "-m", "app.worker.main"]

