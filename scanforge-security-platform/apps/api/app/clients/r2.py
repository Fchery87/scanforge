import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class R2Client:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
    ):
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self._s3 = None
        self._enabled = (
            bool(endpoint and bucket and access_key_id and secret_access_key) and not self._is_placeholder_config()
        )

    def _is_placeholder_config(self) -> bool:
        values = [self.endpoint, self.access_key_id, self.secret_access_key]
        placeholders = ("your-account", "your-access-key", "your-secret-key")
        return any(any(token in value for token in placeholders) for value in values if value)

    @property
    def s3(self):
        if not self._enabled:
            raise RuntimeError("R2 client is not configured")
        if self._s3 is None:
            self._s3 = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )
        return self._s3

    def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 300,
    ) -> str:
        return self.s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )

    def generate_presigned_url(self, key: str, expires_in: int = 300) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def object_size(self, key: str) -> int | None:
        try:
            return int(self.s3.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def read_object(self, key: str, max_bytes: int) -> bytes:
        body = self.s3.get_object(Bucket=self.bucket, Key=key)["Body"]
        try:
            return body.read(max_bytes + 1)
        finally:
            body.close()

    def put_object_if_absent(self, key: str, body: bytes, content_type: str) -> None:
        """Write ``key`` only if nothing exists there (conditional create)."""
        try:
            self.s3.put_object(
                Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, IfNoneMatch="*"
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "412"}:
                raise FileExistsError(key) from exc
            raise

    def delete_object(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)
