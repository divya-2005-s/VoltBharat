"""Tiny in-process TTL cache for read-only analytics queries.

Data changes only when the ETL reloads the database, so a short TTL is safe.
Keys include every argument, so different filters never share an entry.
"""
from __future__ import annotations

import copy
import threading
import time
from functools import wraps
from typing import Any, Callable

from app.core.config import get_settings

_store: dict[tuple, tuple[float, Any]] = {}
_lock = threading.Lock()


def cached(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(conn, *args, **kwargs):
        ttl = get_settings().cache_ttl_seconds
        if ttl <= 0:
            return fn(conn, *args, **kwargs)
        key = (fn.__module__, fn.__qualname__, args, tuple(sorted(kwargs.items())))
        now = time.monotonic()
        with _lock:
            hit = _store.get(key)
        if hit and hit[0] > now:
            return copy.deepcopy(hit[1])  # callers may mutate results
        value = fn(conn, *args, **kwargs)
        with _lock:
            _store[key] = (now + ttl, value)
        return copy.deepcopy(value)

    return wrapper


def clear_cache() -> None:
    with _lock:
        _store.clear()
