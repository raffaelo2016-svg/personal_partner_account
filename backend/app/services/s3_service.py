import asyncio
import uuid
from pathlib import PurePosixPath

import boto3
import structlog
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings

logger = structlog.get_logger()

_s3_client = None
_s3_public_client = None


def _build_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="us-east-1",
    )


def _get_s3():
    global _s3_client  # noqa: PLW0603
    if _s3_client is None:
        _s3_client = _build_client(settings.S3_ENDPOINT)
        try:
            _s3_client.head_bucket(Bucket=settings.S3_BUCKET)
        except ClientError:
            _s3_client.create_bucket(Bucket=settings.S3_BUCKET)
            logger.info("s3_bucket_created", bucket=settings.S3_BUCKET)
    return _s3_client


def _get_s3_public():
    """Клиент для генерации presigned URL, которые отдаются SPA.

    endpoint_url берётся из S3_PUBLIC_ENDPOINT, иначе совпадает с internal.
    """
    global _s3_public_client  # noqa: PLW0603
    if _s3_public_client is None:
        endpoint = settings.S3_PUBLIC_ENDPOINT or settings.S3_ENDPOINT
        _s3_public_client = _build_client(endpoint)
    return _s3_public_client


def upload_file(data: bytes, original_name: str, mime_type: str) -> str:
    ext = PurePosixPath(original_name).suffix.lower()
    s3_key = f"uploads/{uuid.uuid4()}{ext}"

    client = _get_s3()
    client.put_object(
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        Body=data,
        ContentType=mime_type,
    )
    logger.info("s3_file_uploaded", key=s3_key, size=len(data))
    return s3_key


def get_presigned_url(s3_key: str, expires_in: int = 900) -> str:
    client = _get_s3_public()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def delete_file(s3_key: str) -> None:
    client = _get_s3()
    client.delete_object(Bucket=settings.S3_BUCKET, Key=s3_key)
    logger.info("s3_file_deleted", key=s3_key)


def download_file(s3_key: str) -> bytes:
    client = _get_s3()
    response = client.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
    return response["Body"].read()


# ── Async wrappers for use inside async endpoints ────────────────────
# boto3 is sync; run the blocking calls in a worker thread so we don't
# block the event loop.


async def upload_file_async(data: bytes, original_name: str, mime_type: str) -> str:
    return await asyncio.to_thread(upload_file, data, original_name, mime_type)


async def get_presigned_url_async(s3_key: str, expires_in: int = 900) -> str:
    return await asyncio.to_thread(get_presigned_url, s3_key, expires_in)


async def delete_file_async(s3_key: str) -> None:
    await asyncio.to_thread(delete_file, s3_key)


async def download_file_async(s3_key: str) -> bytes:
    return await asyncio.to_thread(download_file, s3_key)
