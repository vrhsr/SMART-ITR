from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import DefaultDict


_firm_upload_counters: DefaultDict[uuid.UUID, list[float]] = defaultdict(list)


def check_firm_upload_rate(*, firm_id: uuid.UUID, max_per_hour: int = 20) -> bool:
    """
    In-memory rate limiter for uploads per firm per hour.

    Returns True if the upload is allowed, False otherwise.
    """

    now = time.time()
    window_start = now - 3600
    events = _firm_upload_counters[firm_id]
    # Drop events older than 1 hour
    _firm_upload_counters[firm_id] = [t for t in events if t >= window_start]
    events = _firm_upload_counters[firm_id]

    if len(events) >= max_per_hour:
        return False

    events.append(now)
    return True

