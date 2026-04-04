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

    def generate_presigned_url(self, key: str, expires_in: int = 300) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
