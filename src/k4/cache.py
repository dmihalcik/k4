"""Tiny TTL cache for completion data under ~/.cache/k4."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "k4"


def cached(name: str, ttl: float, producer: Callable[[], Any]) -> Any:
    """Return cached JSON for ``name`` if fresh, else call ``producer`` and store it."""
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and (time.time() - path.stat().st_mtime) < ttl:
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    value = producer()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value
