FROM python:3.12.8-slim-bookworm@sha256:3cce65a9b53e85a94b8c76bb27bc4eab5049b21c4414ea8f4cdf7dc59b7fddd8

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml .
RUN pip install --no-cache-dir .
COPY apps/api/app ./app
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin api
USER 10001:10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
