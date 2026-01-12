import json
import time
import hashlib
from typing import Optional
from ipaddress import ip_address, ip_network

from fastapi import Request

from open_webui.env import (
    ENV,
    SESSION_TTL_SECONDS,
    REDIS_DB_SESSION,
    TRUSTED_PROXIES,
)
from open_webui.services.redis_client import get_session_client


_SESSION_PREFIX = f"session:{ENV}"
_USER_PREFIX = f"session_user:{ENV}"

_proxy_networks = []
for entry in TRUSTED_PROXIES:
    try:
        _proxy_networks.append(ip_network(entry, strict=False))
    except ValueError:
        continue


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_key(token_hash: str) -> str:
    return f"{_SESSION_PREFIX}:{token_hash}"


def _user_sessions_key(user_id: int) -> str:
    return f"{_USER_PREFIX}:{user_id}"


def get_client_ip(request: Request) -> str:
    client_ip = request.client.host if request.client else ""
    if not _proxy_networks or not client_ip:
        return client_ip or "unknown"

    try:
        client_addr = ip_address(client_ip)
    except ValueError:
        return client_ip

    if any(client_addr in network for network in _proxy_networks):
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            original = forwarded_for.split(",")[0].strip()
            return original or client_ip
    return client_ip


def register_session(user_id: int, token: str, request: Request) -> None:
    client = get_session_client()
    token_hash = _token_hash(token)
    session_key = _session_key(token_hash)
    user_key = _user_sessions_key(user_id)

    payload = {
        "user_id": str(user_id),
        "issued_at": str(int(time.time())),
        "ip": get_client_ip(request),
        "user_agent": request.headers.get("User-Agent", ""),
    }

    pipe = client.pipeline()
    pipe.hset(session_key, mapping=payload)
    pipe.expire(session_key, SESSION_TTL_SECONDS)
    pipe.sadd(user_key, token_hash)
    pipe.expire(user_key, SESSION_TTL_SECONDS)
    pipe.execute()


def validate_and_refresh_session(user_id: int, token: str, request: Optional[Request] = None) -> bool:
    client = get_session_client()
    token_hash = _token_hash(token)
    session_key = _session_key(token_hash)
    user_key = _user_sessions_key(user_id)

    if not client.exists(session_key) or not client.sismember(user_key, token_hash):
        return False

    pipe = client.pipeline()
    pipe.expire(session_key, SESSION_TTL_SECONDS)
    pipe.expire(user_key, SESSION_TTL_SECONDS)
    if request is not None:
        pipe.hset(
            session_key,
            mapping={"ip": get_client_ip(request), "last_seen": str(int(time.time()))},
        )
    pipe.execute()
    return True


def invalidate_session(user_id: int, token: str) -> None:
    client = get_session_client()
    token_hash = _token_hash(token)
    session_key = _session_key(token_hash)
    user_key = _user_sessions_key(user_id)

    pipe = client.pipeline()
    pipe.delete(session_key)
    pipe.srem(user_key, token_hash)
    pipe.execute()


def invalidate_user_sessions(user_id: int) -> int:
    client = get_session_client()
    user_key = _user_sessions_key(user_id)
    token_hashes = client.smembers(user_key)
    if not token_hashes:
        client.delete(user_key)
        return 0

    pipe = client.pipeline()
    for token_hash in token_hashes:
        pipe.delete(_session_key(token_hash))
        pipe.srem(user_key, token_hash)
    pipe.delete(user_key)
    results = pipe.execute()
    # Number of sessions invalidated equals number of token hashes
    return len(token_hashes)


def list_active_sessions(user_id: int):
    client = get_session_client()
    user_key = _user_sessions_key(user_id)
    token_hashes = client.smembers(user_key)
    sessions = []
    for token_hash in token_hashes:
        data = client.hgetall(_session_key(token_hash))
        if data:
            sessions.append({"token_hash": token_hash, **data})
    return sessions
