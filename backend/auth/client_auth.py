from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt

from core.settings import settings


@dataclass(frozen=True)
class ClientToken:
    client_id: uuid.UUID
    firm_id: uuid.UUID


def decode_client_token(token: str) -> ClientToken:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client token") from exc

    client_id_str = payload.get("client_id")
    firm_id_str = payload.get("firm_id")
    if not client_id_str or not firm_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing client token claims")

    try:
        client_id = uuid.UUID(client_id_str)
        firm_id = uuid.UUID(firm_id_str)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client token format") from exc

    return ClientToken(client_id=client_id, firm_id=firm_id)


def get_current_client(
    authorization: str | None = Header(default=None),
) -> ClientToken:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing client bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    return decode_client_token(token)

