from __future__ import annotations

import uuid

from pydantic import BaseModel


class FirmOut(BaseModel):
    firm_id: uuid.UUID
    name: str

