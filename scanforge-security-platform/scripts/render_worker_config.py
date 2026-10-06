#!/usr/bin/env python3
"""Render a dedicated worker environment without copying API-only secrets."""
from __future__ import annotations

import argparse
import os
import re

FORBIDDEN = {
    "DATABASE_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "WORKER_CREDENTIAL_PEPPER",
    "SCHEDULER_API_KEY",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="infra/worker/.env")
    args = parser.parse_args()
    values = {
        "API_BASE_URL": os.environ.get("API_BASE_URL", ""),
        "UPSTASH_REDIS_REST_URL": os.environ.get("UPSTASH_REDIS_REST_URL", ""),
        "UPSTASH_REDIS_REST_TOKEN": os.environ.get("UPSTASH_REDIS_REST_TOKEN", ""),
        "WORKER_CREDENTIAL": os.environ.get("WORKER_CREDENTIAL", ""),
        "WORKER_ORGANIZATION_ID": os.environ.get("WORKER_ORGANIZATION_ID", ""),
        "WORKER_CONSUMER_NAME": os.environ.get("WORKER_CONSUMER_NAME", ""),
        "SCANNER_IMAGE": os.environ.get("SCANNER_IMAGE", ""),
    }
    if any(name in values for name in FORBIDDEN):
        raise RuntimeError("API-only secret attempted to enter worker configuration")
    if not re.fullmatch(r".+@sha256:[0-9a-fA-F]{64}", values["SCANNER_IMAGE"]):
        raise ValueError("SCANNER_IMAGE must be pinned by a 64-character digest")
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"Missing worker configuration: {', '.join(missing)}")
    with open(args.output, "w", encoding="utf-8") as output:
        for name, value in values.items():
            output.write(f"{name}={value}\n")
        output.write("APP_ENV=private-beta\nWORKER_CONCURRENCY=1\nAI_ENABLED=false\n")


if __name__ == "__main__":
    main()
