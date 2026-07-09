from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import aioboto3
    from botocore.exceptions import ClientError
except ImportError:
    raise ImportError("pip install fast-agent-stack[storage-minio]") from None

from fast_agent_stack.core.storage import KeyNotFoundError

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings


class MinIOStorage:
    def __init__(self, settings: BaseSettings) -> None:
        self._bucket = settings.storage_minio_bucket
        self._endpoint = settings.storage_minio_endpoint
        self._timeout = settings.storage_timeout
        self._session = aioboto3.Session(
            aws_access_key_id=settings.storage_minio_access_key or None,
            aws_secret_access_key=settings.storage_minio_secret_key or None,
        )
        self._client = self._session.client(
            "s3",
            endpoint_url=self._endpoint,
        )

    def _client_ctx(self):  # type: ignore[no-untyped-def]
        return self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=None,
            aws_secret_access_key=None,
        )

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        async with self._client_ctx() as client:  # type: ignore[no-untyped-call]
            await client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        return key

    async def download(self, key: str) -> bytes:
        try:
            async with self._client_ctx() as client:  # type: ignore[no-untyped-call]
                resp = await client.get_object(Bucket=self._bucket, Key=key)
                return await resp["Body"].read()  # type: ignore[no-any-return]
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise KeyNotFoundError(key) from exc
            raise

    async def delete(self, key: str) -> None:
        async with self._client_ctx() as client:  # type: ignore[no-untyped-call]
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            async with self._client_ctx() as client:  # type: ignore[no-untyped-call]
                await client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    async def url(self, key: str, *, expires_in: int = 3600) -> str:
        async with self._client_ctx() as client:  # type: ignore[no-untyped-call]
            return await client.generate_presigned_url(  # type: ignore[no-any-return]
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
