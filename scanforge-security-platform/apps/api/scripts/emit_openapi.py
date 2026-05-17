#!/usr/bin/env python3
"""Emit the FastAPI OpenAPI spec to apps/api/openapi.json.

Run from repo root or apps/api/:
    python apps/api/scripts/emit_openapi.py
    python scripts/emit_openapi.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

output = Path(__file__).resolve().parent.parent / "openapi.json"
output.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(f"Wrote {output}", file=sys.stderr)
