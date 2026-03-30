import hashlib
import json
from pathlib import Path


class R2Client:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        public_base_url: str,
    ):
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.public_base_url = (public_base_url or "").rstrip("/")
        self._s3 = None
        self._enabled = bool(endpoint and access_key_id and secret_access_key) and not self._is_placeholder_config()

    def _is_placeholder_config(self) -> bool:
        values = [
            self.endpoint,
            self.access_key_id,
            self.secret_access_key,
        ]
        placeholders = (
            "your-account",
            "your-access-key",
            "your-secret-key",
        )
        return any(any(token in value for token in placeholders) for value in values if value)

    @property
    def s3(self):
        if not self._enabled:
            raise RuntimeError(
                "R2 client is not configured — set real values for R2_ENDPOINT, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, and optionally R2_PUBLIC_BASE_URL"
            )
        if self._s3 is None:
            import boto3
            from botocore.config import Config

            self._s3 = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )
        return self._s3

    def _compute_checksum(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def upload_file(
        self,
        file_path: Path,
        key: str,
        content_type: str = "application/json",
    ) -> dict:
        checksum = self._compute_checksum(file_path)
        file_size = file_path.stat().st_size

        self.s3.upload_file(
            str(file_path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

        return {
            "storage_uri": f"{self.public_base_url}/{key}",
            "checksum_sha256": checksum,
            "size_bytes": file_size,
            "content_type": content_type,
        }

    def upload_raw_output(
        self,
        scan_id: str,
        scanner_name: str,
        output_data: dict,
        format: str = "json",
    ) -> str:
        key = f"scans/{scan_id}/{scanner_name}/raw_output.{format}"

        content = json.dumps(output_data, indent=2)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content.encode(),
            ContentType="application/json",
        )

        return f"{self.public_base_url}/{key}"

    def upload_sarif(
        self,
        scan_id: str,
        scanner_name: str,
        sarif_data: dict,
    ) -> str:
        key = f"scans/{scan_id}/{scanner_name}/results.sarif"

        content = json.dumps(sarif_data, indent=2)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content.encode(),
            ContentType="application/sarif+json",
        )

        return f"{self.public_base_url}/{key}"

    def upload_log(
        self,
        scan_id: str,
        scanner_name: str,
        log_content: str,
    ) -> str:
        key = f"scans/{scan_id}/{scanner_name}/output.log"

        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=log_content.encode(),
            ContentType="text/plain",
        )

        return f"{self.public_base_url}/{key}"

    def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_scan_artifacts(self, scan_id: str) -> None:
        paginator = self.s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix=f"scans/{scan_id}/")

        for page in pages:
            if "Contents" in page:
                keys = [{"Key": obj["Key"]} for obj in page["Contents"]]
                self.s3.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": keys},
                )

    def get_artifact_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"
