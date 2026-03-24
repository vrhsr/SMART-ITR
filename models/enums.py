from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    staff = "staff"

