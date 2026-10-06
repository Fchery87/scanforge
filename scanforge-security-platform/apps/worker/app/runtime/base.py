from __future__ import annotations

import os

from app.runtime.docker import DockerScanRuntime
from app.runtime.local import LocalScanRuntime
from app.runtime.models import ScanRuntime
from app.security.secret_evidence import assert_ai_disabled_for_private_beta


def build_scan_runtime() -> ScanRuntime:
    assert_ai_disabled_for_private_beta()
    environment = os.environ.get("APP_ENV", "development").lower()
    if environment == "private-beta":
        image = os.environ.get("SCANNER_IMAGE", "")
        return DockerScanRuntime(image=image)
    return LocalScanRuntime()
