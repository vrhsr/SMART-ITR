from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import boto3

from core.settings import settings


def generate_client_upload_url(
    *,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    filename: str,
    bucket: str,
    kms_key_id: str,
    expires_in_minutes: int = 15,
) -> dict[str, str]:
    """
    Generate a pre-signed S3 URL for client uploads.

    This does not require a Cognito account and should be used to allow
    end clients to upload documents directly, while enforcing KMS encryption.
    """

    s3 = boto3.client("s3", region_name=settings.aws_region)
    key = f"firms/{firm_id}/clients/{client_id}/{uuid.uuid4()}-{filename}"

    expires_in_seconds = int(timedelta(minutes=expires_in_minutes).total_seconds())

    params = {
        "Bucket": bucket,
        "Key": key,
        "ServerSideEncryption": "aws:kms",
        "SSEKMSKeyId": kms_key_id,
    }

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params=params,
        ExpiresIn=expires_in_seconds,
    )

    return {
        "upload_url": url,
        "bucket": bucket,
        "key": key,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat(),
    }

