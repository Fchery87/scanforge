from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx


class R2Client:
    """Upload artifacts through API-issued exact-key presigned URLs."""

    def __init__(
        self,
        api_base_url: str,
        worker_credential: str,
        *,
        request_timeout: float = 60.0,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.worker_credential = worker_credential
        self.request_timeout = request_timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Worker-Credential": self.worker_credential}

    def _compute_checksum(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with file_path.open("rb") as artifact:
            for chunk in iter(lambda: artifact.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _upload(
        self,
        *,
        organization_id: str,
        scan_id: str,
        scanner_name: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        request = {
            "scanner_name": scanner_name,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(content),
        }
        async with httpx.AsyncClient(
            timeout=self.request_timeout,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"{self.api_base_url}/api/v1/internal/scans/{scan_id}/artifacts/upload-url",
                json=request,
                headers=self._headers,
            )
            response.raise_for_status()
            upload = response.json()
            expected_key = f"scan-artifacts/{organization_id}/{scan_id}/{scanner_name}/{filename}"
            if upload["key"] != expected_key:
                raise RuntimeError("API returned an artifact key outside the requested tenant scope")
            uploaded = await client.put(
                upload["upload_url"],
                content=content,
                headers={"Content-Type": content_type},
            )
            uploaded.raise_for_status()
            return upload["key"]

    async def upload_file(
        self,
        file_path: Path,
        key: str,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        parts = key.split("/")
        if len(parts) != 5 or parts[0] != "scan-artifacts":
            raise ValueError("artifact key must be tenant-scoped")
        _, organization_id, scan_id, scanner_name, filename = parts
        content = file_path.read_bytes()
        storage_uri = await self._upload(
            organization_id=organization_id,
            scan_id=scan_id,
            scanner_name=scanner_name,
            filename=filename,
            content=content,
            content_type=content_type,
        )
        return {
            "storage_uri": storage_uri,
            "checksum_sha256": self._compute_checksum(file_path),
            "size_bytes": len(content),
            "content_type": content_type,
        }

    async def upload_raw_output(
        self,
        organization_id: str,
        scan_id: str,
        scanner_name: str,
        output_data: dict | list,
        format: str = "json",
    ) -> str:
        return await self._upload(
            organization_id=organization_id,
            scan_id=scan_id,
            scanner_name=scanner_name,
            filename=f"raw_output.{format}",
            content=json.dumps(output_data, separators=(",", ":")).encode(),
            content_type="application/json",
        )
