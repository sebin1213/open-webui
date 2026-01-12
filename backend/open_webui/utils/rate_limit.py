import time
from typing import Optional

from fastapi import HTTPException

from open_webui.env import (
    ENV,
    RATE_LIMIT_DEFAULT_PER_MIN,
)
from open_webui.services.redis_client import get_cache_client
from open_webui.utils.session_store import get_client_ip


_RATE_LIMIT_PREFIX = f"rl:{ENV}"
_DEFAULT_WINDOW = 60


def _current_window(window_seconds: int) -> int:
    return int(time.time() // window_seconds)


def enforce_rate_limit(
    *,
    identifier: str,
    route: str,
    limit: int,
    window_seconds: int,
    detail: Optional[str] = None,
) -> None:
    if limit <= 0:
        return

    client = get_cache_client(decode=False)
    window = _current_window(window_seconds)
    key = f"{_RATE_LIMIT_PREFIX}:{route}:{identifier}:{window}"
    pipe = client.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, window_seconds)
    count, _ = pipe.execute()
    if int(count) > limit:
        raise HTTPException(status_code=429, detail=detail or "Rate limit exceeded")


def enforce_default_rate_limit(request, user_id: Optional[int], route: str) -> None:
    limit = RATE_LIMIT_DEFAULT_PER_MIN
    if limit <= 0:
        return
    identifier = str(user_id) if user_id else get_client_ip(request)
    enforce_rate_limit(
        identifier=identifier,
        route=route,
        limit=limit,
        window_seconds=_DEFAULT_WINDOW,
    )
