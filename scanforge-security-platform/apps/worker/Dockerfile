FROM python:3.12.8-slim-bookworm@sha256:3cce65a9b53e85a94b8c76bb27bc4eab5049b21c4414ea8f4cdf7dc59b7fddd8

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git docker.io \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/worker/pyproject.toml apps/worker/constraints.txt ./
RUN pip install --no-cache-dir -c constraints.txt --upgrade pip \
    && pip install --no-cache-dir -c constraints.txt .
COPY apps/worker/app ./app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin worker
USER 10001:10001
CMD ["python", "-m", "app.worker.main"]
