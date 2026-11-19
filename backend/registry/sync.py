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
  get_changelog()      — returns the versioned sync history list
  apply_bulletin()     — apply a simulated FDA/EMA regulatory bulletin update
                         with a full audit-trail diff entry

Design: file-based reload from synthetic_data/ (architecture.md §12).
Versioned sync history added per idea.txt requirement.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Registry state ────────────────────────────────────────────────────────────
_registry_cache: List[Dict[str, Any]] = []
_last_sync: Optional[datetime] = None

# ── Versioned changelog ───────────────────────────────────────────────────────
# Each entry: {sync_version, timestamp, source, changes: [{medication_id, field, old, new}]}
_changelog: List[Dict[str, Any]] = []
_changelog_lock = threading.Lock()

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


def _next_version() -> str:
    """Generate a monotonically increasing version string v1, v2, …"""
    with _changelog_lock:
        return f"v{len(_changelog) + 1}"


def reload_registry(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Load (or reload) the registry from disk into the in-process cache.

    Records a versioned changelog entry with an empty diff (full reload —
    no field-level diff is computed for a wholesale file reload).

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

    _append_changelog(
        source="file_reload",
        changes=[],
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
    Does NOT append a changelog entry so test state stays clean.
    """
    global _registry_cache, _last_sync
    _registry_cache = list(records)
    _last_sync = datetime.now(tz=timezone.utc)


# ── Versioned changelog helpers ───────────────────────────────────────────────

def _append_changelog(
    source: str,
    changes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Append a new versioned entry to the in-memory changelog and return it.

    Parameters
    ──────────
    source  : Human-readable source label, e.g. 'FDA Orange Book', 'EU Union Register'.
    changes : List of field-level diff dicts:
              [{"medication_id": str, "field": str, "old_value": Any, "new_value": Any}]
    """
    with _changelog_lock:
        version = f"v{len(_changelog) + 1}"
        entry: Dict[str, Any] = {
            "sync_version": version,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "source": source,
            "changes": changes,
        }
        _changelog.append(entry)
    return entry


def get_changelog() -> List[Dict[str, Any]]:
    """Return the full versioned sync changelog (most recent first)."""
    with _changelog_lock:
        return list(reversed(_changelog))


def clear_changelog() -> None:
    """Test helper — wipes the changelog state."""
    global _changelog
    with _changelog_lock:
        _changelog.clear()


def apply_bulletin(
    medication_id: str,
    source: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Simulate ingesting a regulatory bulletin from FDA or EMA.

    Finds the medication record by ``medication_id``, applies the ``updates``
    dict as field patches, computes a field-level diff, and records a versioned
    changelog entry.

    Parameters
    ──────────
    medication_id : UUID of the medication record to update.
    source        : Registry source label, e.g. 'FDA Orange Book', 'EU Union Register'.
    updates       : Dict of field → new value.  Only fields already present on
                    the record are allowed; unknown fields are silently skipped.

    Returns
    ───────
    The new changelog entry, or ``None`` if the medication_id was not found.
    """
    global _registry_cache

    # Locate the record
    target_idx: Optional[int] = None
    for idx, rec in enumerate(_registry_cache):
        if rec.get("medication_id") == medication_id:
            target_idx = idx
            break

    if target_idx is None:
        logger.warning("apply_bulletin: medication_id %s not found", medication_id)
        return None

    old_record = copy.deepcopy(_registry_cache[target_idx])
    changes: List[Dict[str, Any]] = []

    for field, new_value in updates.items():
        if field not in old_record:
            # Only update existing fields (data minimization guard)
            continue
        old_value = old_record[field]
        if old_value != new_value:
            changes.append(
                {
                    "medication_id": medication_id,
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value,
                }
            )
            _registry_cache[target_idx][field] = new_value

    # Always stamp last_updated regardless of whether other fields changed
    now_iso = datetime.now(tz=timezone.utc).date().isoformat()
    if _registry_cache[target_idx].get("last_updated") != now_iso:
        changes.append(
            {
                "medication_id": medication_id,
                "field": "last_updated",
                "old_value": old_record.get("last_updated"),
                "new_value": now_iso,
            }
        )
        _registry_cache[target_idx]["last_updated"] = now_iso

    global _last_sync
    _last_sync = datetime.now(tz=timezone.utc)

    return _append_changelog(source=source, changes=changes)
