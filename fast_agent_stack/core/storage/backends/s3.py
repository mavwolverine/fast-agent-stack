from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import aioboto3
    from botocore.exceptions import ClientError
except ImportError:
    raise ImportError("pip install fast-agent-stack[storage-s3]") from None

from fast_agent_stack.core.storage import KeyNotFoundError

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings


class S3Storage:
    def __init__(self, settings: BaseSettings) -> None:
        self._bucket = settings.storage_s3_bucket
        self._region = settings.storage_s3_region
        self._timeout = settings.storage_timeout
        self._session = aioboto3.Session()
        self._client = self._session.client(
            "s3",
            region_name=self._region,
        )

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        async with self._session.client("s3", region_name=self._region) as client:
            await client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        return key

    async def download(self, key: str) -> bytes:
        try:
            async with self._session.client("s3", region_name=self._region) as client:
                resp = await client.get_object(Bucket=self._bucket, Key=key)
                return await resp["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise KeyNotFoundError(key) from exc
            raise

    async def delete(self, key: str) -> None:
        async with self._session.client("s3", region_name=self._region) as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            async with self._session.client("s3", region_name=self._region) as client:
                await client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    async def url(self, key: str, *, expires_in: int = 3600) -> str:
        async with self._session.client("s3", region_name=self._region) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
