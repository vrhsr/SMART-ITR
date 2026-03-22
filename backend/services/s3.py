from __future__ import annotations

import boto3

from core.settings import settings


def put_encrypted_object(*, bucket: str, key: str, data: bytes, kms_key_id: str) -> None:
    """
    Upload object to S3 with SSE-KMS encryption.
    """

    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=kms_key_id,
        ContentType="application/pdf",
    )

