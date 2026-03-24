from __future__ import annotations

from typing import Any

import boto3

from core.settings import settings


def create_cognito_user_pool(*, pool_name: str) -> dict[str, Any]:
    """
    Create (or configure) a Cognito user pool for SmartITR.

    This config focuses on:
    - email + phone_number as primary attributes
    - custom:firm_id attribute to link users to tenants
    """

    client = boto3.client("cognito-idp", region_name=settings.aws_region)
    response = client.create_user_pool(
        PoolName=pool_name,
        AutoVerifiedAttributes=["email", "phone_number"],
        AliasAttributes=["email"],
        Schema=[
            {"Name": "email", "AttributeDataType": "String", "Required": True},
            {"Name": "phone_number", "AttributeDataType": "String", "Required": True},
            {"Name": "custom:firm_id", "AttributeDataType": "String", "Required": False},
            {"Name": "custom:role", "AttributeDataType": "String", "Required": False},
        ],
    )
    return response


def create_cognito_user_pool_client(*, pool_id: str, client_name: str) -> dict[str, Any]:
    """
    Create a user pool client for web usage.

    Note: embedding firm_id/role into JWTs typically uses custom attributes
    and Cognito Lambda triggers; this function only sets up the client.
    """

    client = boto3.client("cognito-idp", region_name=settings.aws_region)
    response = client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=client_name,
        GenerateSecret=False,
        ExplicitAuthFlows=[
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
            "ALLOW_USER_SRP_AUTH",
        ],
        SupportedIdentityProviders=["COGNITO"],
    )
    return response

