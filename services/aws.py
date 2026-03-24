from __future__ import annotations

from core.settings import settings


def get_aws_region() -> str:
    """
    SmartITR must operate in AWS Mumbai only (ap-south-1).
    """

    return settings.aws_region

