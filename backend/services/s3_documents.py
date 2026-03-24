from __future__ import annotations

import uuid

import boto3

from core.settings import settings


def download_pdf_to_memory(*, bucket: str, key: str) -> bytes:
    """
    Download a PDF from S3 to memory.

    Never write to disk.
    """

    s3 = boto3.client("s3", region_name=settings.aws_region)
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    if not isinstance(body, (bytes, bytearray)):
        raise ValueError("S3 object body was not bytes")
    return bytes(body)


def ensure_sse_kms(*, head_object: dict, kms_key_id: str | None) -> None:
    """
    Validate the object is KMS encrypted (SSE-KMS).
    """

    algo = head_object.get("ServerSideEncryption")
    if algo != "aws:kms":
        raise ValueError("S3 object is not SSE-KMS encrypted")

    if kms_key_id:
        kid = head_object.get("SSEKMSKeyId")
        if kid and kms_key_id not in kid:
            raise ValueError("Unexpected KMS key id")

