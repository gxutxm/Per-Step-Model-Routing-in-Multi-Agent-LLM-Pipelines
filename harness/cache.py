"""Disk cache for model responses.

This file writes one JSON file per request under ``cache/``. A later
call with the same model and messages reads that file instead of
calling the provider.
"""

import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


def cache_key(model: str, messages: list[dict]) -> str:
    """Return a stable hash of the model name and messages."""
    payload = json.dumps(
        {"model": model, "messages": messages},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get(model: str, messages: list[dict]) -> dict | None:
    """Return the stored response, or None if this request has not been cached."""
    path = CACHE_DIR / f"{cache_key(model, messages)}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def put(model: str, messages: list[dict], response: dict) -> None:
    """Store a response so the same request can be served from disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{cache_key(model, messages)}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
