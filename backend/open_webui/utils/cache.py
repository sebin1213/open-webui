from urllib.parse import urlparse, parse_qs

from aiocache import caches, cached as aiocache_cached
import redis

from open_webui.env import (
    REDIS_SOCKET_PATH,
    REDIS_URL,
    REDIS_DB_CACHE,
    CACHE_TTL_SECONDS_DEFAULT,
    ENV,
)


def _build_cache_kwargs() -> dict:
    if REDIS_SOCKET_PATH:
        return {
            "endpoint": "localhost",
            "port": 0,
            "db": int(REDIS_DB_CACHE),
            "connection_pool_kwargs": {
                "connection_class": redis.connection.UnixDomainSocketConnection,
                "path": REDIS_SOCKET_PATH,
            },
        }

    if REDIS_URL:
        parsed = urlparse(REDIS_URL)
        query = parse_qs(parsed.query)

        conn_kwargs = {
            "endpoint": parsed.hostname or "127.0.0.1",
            "port": int(parsed.port or 6379),
            "db": int(REDIS_DB_CACHE),
        }

        path_db = parsed.path.lstrip("/") if parsed.path else ""
        if path_db:
            try:
                conn_kwargs["db"] = int(path_db)
            except ValueError:
                pass
        elif "db" in query and query["db"]:
            try:
                conn_kwargs["db"] = int(query["db"][0])
            except (ValueError, TypeError):
                pass

        if parsed.username:
            conn_kwargs["username"] = parsed.username

        if parsed.password:
            conn_kwargs["password"] = parsed.password

        if parsed.scheme.lower() == "rediss":
            conn_kwargs["ssl"] = True

        return conn_kwargs

    return {"endpoint": "127.0.0.1", "port": 6379, "db": int(REDIS_DB_CACHE)}


cache_connection_kwargs = _build_cache_kwargs()

caches.set_config(
    {
        "default": {
            "cache": "aiocache.RedisCache",
            "ttl": CACHE_TTL_SECONDS_DEFAULT,
            "namespace": f"cache:{ENV}",
            "serializer": {"class": "aiocache.serializers.PickleSerializer"},
            **cache_connection_kwargs,
        }
    }
)


def cached(*args, **kwargs):
    kwargs.setdefault("alias", "default")
    kwargs.setdefault("ttl", CACHE_TTL_SECONDS_DEFAULT)
    return aiocache_cached(*args, **kwargs)
