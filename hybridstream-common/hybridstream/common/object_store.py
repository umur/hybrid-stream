import aioboto3
from botocore.config import Config


class ObjectStore:
    """aioboto3-backed async object store for MinIO/S3 snapshot storage."""

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ):
        self._session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self._endpoint = endpoint_url
        self._bucket = bucket
        self._config = Config(retries={"max_attempts": 3, "mode": "adaptive"})

    async def upload(self, key: str, data: bytes) -> int:
        """Upload bytes; returns byte size. Idempotent (overwrite safe)."""
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            config=self._config,
        ) as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=data)
        return len(data)

    async def download(self, key: str) -> bytes:
        """Download bytes by key."""
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            config=self._config,
        ) as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=key)
            return await response["Body"].read()

    async def exists(self, key: str) -> bool:
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            config=self._config,
        ) as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except s3.exceptions.ClientError:
                return False
