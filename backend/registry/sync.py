"""
backend/registry/sync.py
─────────────────────────
Registry sync stub: reloads the medication registry JSON from
synthetic_data/medication_registry.json into an in-process cache.

In production this module would be extended to call real FDA/EMA APIs.
For the MVP it simulates "scheduled sync" by reading the local file on
demand or at a configurable interval.

The module exposes:
  get_registry()       — returns the current in-memory registry list
  reload_registry()    — reloads from disk and returns updated list
  last_sync_time()     — returns the datetime of the last successful load

Design: file-based reload from synthetic_data/ (architecture.md §12).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Registry state ────────────────────────────────────────────────────────────
_registry_cache: List[Dict[str, Any]] = []
_last_sync: Optional[datetime] = None

# ── Default path (resolved relative to repo root) ────────────────────────────
_DEFAULT_REGISTRY_PATH = (
    Path(__file__).parent.parent.parent / "synthetic_data" / "medication_registry.json"
)


def _load_from_file(path: Path) -> List[Dict[str, Any]]:
    """Read and parse the registry JSON file. Raises if file is missing or malformed."""
    if not path.exists():
        raise FileNotFoundError(
            f"Medication registry file not found: {path}. "
            "Run scripts/generate_synthetic_data.py first."
        )
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}")
    return data


def reload_registry(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Load (or reload) the registry from disk into the in-process cache.

    Parameters
    ──────────
    path : Optional path override. Defaults to synthetic_data/medication_registry.json
           relative to repo root.

    Returns
    ───────
    The freshly loaded registry list.
    """
    global _registry_cache, _last_sync

    target = path or _DEFAULT_REGISTRY_PATH
    _registry_cache = _load_from_file(target)
    _last_sync = datetime.now(tz=timezone.utc)
    logger.info(
        "Registry reloaded: %d records from %s at %s",
        len(_registry_cache),
        target,
        _last_sync.isoformat(),
    )
    return _registry_cache


def get_registry(auto_load: bool = True) -> List[Dict[str, Any]]:
    """
    Return the current in-memory registry.

    Parameters
    ──────────
    auto_load : If True (default) and the cache is empty, attempt to load
                from disk automatically. Set to False in tests to inject
                data manually.
    """
    if not _registry_cache and auto_load:
        try:
            reload_registry()
        except FileNotFoundError:
            logger.warning(
                "Registry file not found on auto-load. "
                "Returning empty list. Run generate_synthetic_data.py."
            )
    return list(_registry_cache)


def last_sync_time() -> Optional[datetime]:
    """Return the UTC datetime of the last successful registry load, or None."""
    return _last_sync


def inject_registry(records: List[Dict[str, Any]]) -> None:
    """
    Inject a list of records directly into the cache (test helper).

    This bypasses disk I/O entirely — useful for unit tests that need
    a known registry state without touching the filesystem.
    """
    global _registry_cache, _last_sync
    _registry_cache = list(records)
    _last_sync = datetime.now(tz=timezone.utc)
