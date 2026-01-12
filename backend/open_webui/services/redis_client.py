import redis
from functools import lru_cache
from typing import Any, Dict

from open_webui.env import (
    REDIS_SOCKET_PATH,
    REDIS_URL,
    REDIS_DB_SESSION,
    REDIS_DB_CACHE,
)


def _build_connection_kwargs(db: int, decode: bool = True) -> Dict[str, Any]:
    """Prepare keyword arguments for redis client constructors."""
    kwargs: Dict[str, Any] = {"db": db, "decode_responses": decode}
    if REDIS_SOCKET_PATH:
        kwargs["unix_socket_path"] = REDIS_SOCKET_PATH
        return kwargs
    if REDIS_URL:
        kwargs["url"] = REDIS_URL
        return kwargs
    raise RuntimeError("Redis is not configured. Set REDIS_SOCKET_PATH or REDIS_URL.")


@lru_cache(maxsize=8)
def _get_sync_client(db: int, decode: bool) -> redis.Redis:
    kwargs = _build_connection_kwargs(db=db, decode=decode)
    if "url" in kwargs:
        url = kwargs.pop("url")
        return redis.Redis.from_url(url, **kwargs)
    return redis.Redis(**kwargs)


def get_session_client() -> redis.Redis:
    """Redis connection for session management."""
    return _get_sync_client(REDIS_DB_SESSION, True)


def get_cache_client(decode: bool = False) -> redis.Redis:
    """Redis connection for cache/rate-limit usage."""
    return _get_sync_client(REDIS_DB_CACHE, decode)

