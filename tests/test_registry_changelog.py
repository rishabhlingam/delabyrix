"""
tests/test_registry_changelog.py
──────────────────────────────────
Unit tests for the versioned registry sync changelog (idea.txt requirement):
  - backend/registry/sync.py  — apply_bulletin(), get_changelog(), clear_changelog()
  - backend/routers/registry.py  — POST /registry/sync, GET /registry/changelog

All tests inject synthetic data via inject_registry() to bypass disk I/O.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.registry.sync import (
    apply_bulletin,
    clear_changelog,
    get_changelog,
    get_registry,
    inject_registry,
)
from backend.routers.registry import router as registry_router
from backend.synthetic.medication_registry import generate_medication_registry


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_registry():
    """Inject a known registry and wipe the changelog before every test."""
    clear_changelog()
    inject_registry(generate_medication_registry())
    yield
    clear_changelog()
    inject_registry([])


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(registry_router)
    return TestClient(app, raise_server_exceptions=True)


def _first_medication_id(jurisdiction: str = "US_FDA") -> str:
    """Return the medication_id of the first record for the given jurisdiction."""
    for rec in get_registry(auto_load=False):
        if rec.get("jurisdiction") == jurisdiction:
            return rec["medication_id"]
    raise RuntimeError(f"No {jurisdiction} record found in synthetic registry")


# ══════════════════════════════════════════════════════════════════════════════
# apply_bulletin() unit tests
# ══════════════════════════════════════════════════════════════════════════════

class TestApplyBulletin:

    def test_returns_changelog_entry_on_success(self):
        med_id = _first_medication_id("US_FDA")
        entry = apply_bulletin(
            medication_id=med_id,
            source="FDA Orange Book",
            updates={"status": "restricted"},
        )
        assert entry is not None
        assert "sync_version" in entry
        assert "timestamp" in entry
        assert entry["source"] == "FDA Orange Book"
        assert isinstance(entry["changes"], list)

    def test_changelog_entry_contains_field_diff(self):
        """Changing status must produce a changes entry with old_value / new_value."""
        med_id = _first_medication_id("US_FDA")
        # Grab the current status so we can verify the diff
        old_status = next(
            rec["status"] for rec in get_registry(auto_load=False)
            if rec["medication_id"] == med_id
        )
        entry = apply_bulletin(
            medication_id=med_id,
            source="FDA Orange Book",
            updates={"status": "delisted"},
        )
        status_change = next(
            (c for c in entry["changes"] if c["field"] == "status"), None
        )
        assert status_change is not None
        assert status_change["old_value"] == old_status
        assert status_change["new_value"] == "delisted"
        assert status_change["medication_id"] == med_id

    def test_unknown_medication_returns_none(self):
        entry = apply_bulletin(
            medication_id="00000000-0000-0000-0000-000000000000",
            source="FDA Orange Book",
            updates={"status": "restricted"},
        )
        assert entry is None

    def test_unknown_field_is_silently_skipped(self):
        """Fields not on the record must not raise and must not appear in changes."""
        med_id = _first_medication_id("US_FDA")
        entry = apply_bulletin(
            medication_id=med_id,
            source="FDA Orange Book",
            updates={"nonexistent_field": "value"},
        )
        # entry still created but changes only include last_updated (always stamped)
        assert entry is not None
        field_names = [c["field"] for c in entry["changes"]]
        assert "nonexistent_field" not in field_names

    def test_last_updated_always_stamped(self):
        med_id = _first_medication_id("EU_EMA")
        entry = apply_bulletin(
            medication_id=med_id,
            source="EU Union Register",
            updates={"restriction_reason": "Withdrawn pending review."},
        )
        field_names = [c["field"] for c in entry["changes"]]
        assert "last_updated" in field_names

    def test_multiple_bulletins_increment_version(self):
        med_id = _first_medication_id("US_FDA")
        e1 = apply_bulletin(med_id, "FDA Orange Book", {"status": "restricted"})
        e2 = apply_bulletin(med_id, "FDA Orange Book", {"restriction_reason": "Updated."})
        assert e1["sync_version"] != e2["sync_version"]
        # Versions are v1, v2, … (monotonically increasing)
        v1 = int(e1["sync_version"].lstrip("v"))
        v2 = int(e2["sync_version"].lstrip("v"))
        assert v2 == v1 + 1


# ══════════════════════════════════════════════════════════════════════════════
# get_changelog() unit tests
# ══════════════════════════════════════════════════════════════════════════════

class TestGetChangelog:

    def test_empty_changelog_on_fresh_start(self):
        # autouse fixture clears changelog
        assert get_changelog() == []

    def test_changelog_grows_with_bulletins(self):
        med_id = _first_medication_id("US_FDA")
        apply_bulletin(med_id, "FDA Orange Book", {"status": "restricted"})
        apply_bulletin(med_id, "FDA Orange Book", {"status": "approved"})
        changelog = get_changelog()
        assert len(changelog) == 2

    def test_changelog_ordered_newest_first(self):
        med_id = _first_medication_id("US_FDA")
        apply_bulletin(med_id, "FDA Orange Book", {"status": "restricted"})
        apply_bulletin(med_id, "FDA Orange Book", {"status": "approved"})
        changelog = get_changelog()
        # Second bulletin was applied last → should be first in output
        v_first = int(changelog[0]["sync_version"].lstrip("v"))
        v_second = int(changelog[1]["sync_version"].lstrip("v"))
        assert v_first > v_second

    def test_changelog_entry_schema(self):
        med_id = _first_medication_id("US_FDA")
        apply_bulletin(med_id, "FDA Orange Book", {"status": "restricted"})
        entry = get_changelog()[0]
        assert set(entry.keys()) >= {"sync_version", "timestamp", "source", "changes"}

    def test_clear_changelog(self):
        med_id = _first_medication_id("US_FDA")
        apply_bulletin(med_id, "FDA Orange Book", {"status": "restricted"})
        clear_changelog()
        assert get_changelog() == []


# ══════════════════════════════════════════════════════════════════════════════
# POST /registry/sync  API tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRegistrySyncEndpoint:

    def test_post_sync_returns_200_on_valid_bulletin(self, client):
        med_id = _first_medication_id("US_FDA")
        resp = client.post(
            "/registry/sync",
            json={
                "medication_id": med_id,
                "source": "FDA Orange Book",
                "updates": {"status": "restricted"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sync_version" in data
        assert data["source"] == "FDA Orange Book"
        assert isinstance(data["changes"], list)

    def test_post_sync_returns_404_for_unknown_medication(self, client):
        resp = client.post(
            "/registry/sync",
            json={
                "medication_id": "00000000-0000-0000-0000-000000000000",
                "source": "FDA Orange Book",
                "updates": {"status": "banned"},
            },
        )
        assert resp.status_code == 404

    def test_post_sync_returns_400_for_no_mutable_fields(self, client):
        med_id = _first_medication_id("US_FDA")
        resp = client.post(
            "/registry/sync",
            json={
                "medication_id": med_id,
                "source": "FDA Orange Book",
                "updates": {"name_generic": "hacked"},  # immutable field
            },
        )
        assert resp.status_code == 400

    def test_post_sync_diff_reflected_in_registry(self, client):
        """After a successful sync, the in-memory registry record is updated."""
        med_id = _first_medication_id("EU_EMA")
        new_reason = "EMA safety bulletin 2026: temporary restriction."
        client.post(
            "/registry/sync",
            json={
                "medication_id": med_id,
                "source": "EU Union Register",
                "updates": {
                    "status": "restricted",
                    "restriction_reason": new_reason,
                },
            },
        )
        updated = next(
            rec for rec in get_registry(auto_load=False)
            if rec["medication_id"] == med_id
        )
        assert updated["status"] == "restricted"
        assert updated["restriction_reason"] == new_reason


# ══════════════════════════════════════════════════════════════════════════════
# GET /registry/changelog  API tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRegistryChangelogEndpoint:

    def test_get_changelog_returns_empty_list_initially(self, client):
        resp = client.get("/registry/changelog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entries"] == 0
        assert data["entries"] == []

    def test_get_changelog_reflects_posted_bulletin(self, client):
        med_id = _first_medication_id("US_FDA")
        client.post(
            "/registry/sync",
            json={
                "medication_id": med_id,
                "source": "FDA Orange Book",
                "updates": {
                    "restriction_reason": "Test bulletin: flagged for safety review.",
                },
            },
        )
        resp = client.get("/registry/changelog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entries"] == 1
        entry = data["entries"][0]
        assert entry["source"] == "FDA Orange Book"
        # At minimum, last_updated is always stamped
        assert len(entry["changes"]) >= 1

    def test_get_changelog_limit_param(self, client):
        med_id = _first_medication_id("US_FDA")
        for i in range(5):
            client.post(
                "/registry/sync",
                json={
                    "medication_id": med_id,
                    "source": "FDA Orange Book",
                    "updates": {"status": "restricted" if i % 2 == 0 else "approved"},
                },
            )
        resp = client.get("/registry/changelog", params={"limit": 3})
        data = resp.json()
        assert data["total_entries"] == 5
        assert len(data["entries"]) == 3

    def test_get_changelog_entries_newest_first(self, client):
        med_id_fda = _first_medication_id("US_FDA")
        med_id_ema = _first_medication_id("EU_EMA")
        client.post(
            "/registry/sync",
            json={
                "medication_id": med_id_fda,
                "source": "FDA Orange Book",
                "updates": {"status": "restricted"},
            },
        )
        client.post(
            "/registry/sync",
            json={
                "medication_id": med_id_ema,
                "source": "EU Union Register",
                "updates": {"status": "banned"},
            },
        )
        resp = client.get("/registry/changelog")
        entries = resp.json()["entries"]
        # Newest first → EU Union Register should be first
        assert entries[0]["source"] == "EU Union Register"
        assert entries[1]["source"] == "FDA Orange Book"
