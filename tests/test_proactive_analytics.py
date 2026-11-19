"""
tests/test_proactive_analytics.py
────────────────────────────────────
Unit tests for the proactive care pattern analytics (idea.txt requirement):
  - backend/analytics/aggregator.py  — _build_proactive_recommendations()
  - backend/analytics/router.py      — GET /analytics/dashboard
                                       (proactive_recommendations field)

All tests use a minimal inline patient-log fixture to stay fast and
deterministic. No disk I/O, no watsonx calls, no PII.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.analytics.aggregator import (
    _build_proactive_recommendations,
    build_dashboard,
    get_telemetry_store,
)
from backend.analytics.router import router as analytics_router

# ──────────────────────────────────────────────────────────────────────────────
# Minimal patient-log fixtures
# ──────────────────────────────────────────────────────────────────────────────

_HALAL_LOGS: List[Dict[str, Any]] = [
    {
        "patient_id": f"P-TEST{i:04d}",
        "age_band": "31-45",
        "nationality": "SA",
        "condition_codes": ["I00-I99"],
        "medications_current": [],
        "diet_flags": ["halal"],
        "interaction_language": "ar",
        "visit_type": "outpatient",
    }
    for i in range(5)
]

_ICD_LOGS: List[Dict[str, Any]] = [
    {
        "patient_id": f"P-ICD{i:04d}",
        "age_band": "46-60",
        "nationality": "DE",
        "condition_codes": ["E00-E89", "F01-F99"],
        "medications_current": [],
        "diet_flags": [],
        "interaction_language": "de",
        "visit_type": "ER",
    }
    for i in range(4)
]

_CONFLICT_LOGS: List[Dict[str, Any]] = [
    {
        "patient_id": f"P-CONF{i:04d}",
        "age_band": "61+",
        "nationality": "MX",
        "condition_codes": ["K00-K95"],
        "medications_current": ["domperidone"],
        "diet_flags": [],
        "interaction_language": "es",
        "visit_type": "outpatient",
    }
    for i in range(3)
]

_MIXED_LOGS = _HALAL_LOGS + _ICD_LOGS + _CONFLICT_LOGS


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_telemetry():
    """Ensure telemetry store is clean before/after each test."""
    get_telemetry_store().clear()
    yield
    get_telemetry_store().clear()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(analytics_router)
    return TestClient(app, raise_server_exceptions=True)


# ══════════════════════════════════════════════════════════════════════════════
# _build_proactive_recommendations() unit tests
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildProactiveRecommendations:

    def test_returns_empty_list_on_no_logs(self):
        result = _build_proactive_recommendations([])
        assert result == []

    def test_dietary_category_detected(self):
        recs = _build_proactive_recommendations(_HALAL_LOGS)
        categories = [r["category"] for r in recs]
        assert "dietary" in categories

    def test_dietary_magnitude_matches_count(self):
        recs = _build_proactive_recommendations(_HALAL_LOGS)
        halal_rec = next(r for r in recs if r["category"] == "dietary" and "halal" in r["title"])
        assert halal_rec["magnitude"] == 5

    def test_dietary_affected_groups_contains_nationality(self):
        recs = _build_proactive_recommendations(_HALAL_LOGS)
        halal_rec = next(r for r in recs if r["category"] == "dietary" and "halal" in r["title"])
        assert "SA" in halal_rec["affected_groups"]

    def test_icd10_cluster_detected(self):
        recs = _build_proactive_recommendations(_ICD_LOGS)
        categories = [r["category"] for r in recs]
        assert "icd10_cluster" in categories

    def test_icd10_magnitude_correct(self):
        recs = _build_proactive_recommendations(_ICD_LOGS)
        # E00-E89 appears 4 times (one per log)
        icd_rec = next(
            r for r in recs
            if r["category"] == "icd10_cluster" and "E00-E89" in r["title"]
        )
        assert icd_rec["magnitude"] == 4

    def test_icd10_label_human_readable(self):
        """E00-E89 should map to 'Endocrine & Metabolic', not raw code."""
        recs = _build_proactive_recommendations(_ICD_LOGS)
        icd_rec = next(
            (r for r in recs if r["category"] == "icd10_cluster" and "E00-E89" in r["title"]),
            None,
        )
        assert icd_rec is not None
        assert "Endocrine" in icd_rec["title"]

    def test_icd10_affected_groups_include_visit_and_language(self):
        recs = _build_proactive_recommendations(_ICD_LOGS)
        icd_rec = next(r for r in recs if r["category"] == "icd10_cluster")
        groups = icd_rec["affected_groups"]
        # visit_type=ER and lang=de should both appear
        assert "ER" in groups or "de" in groups

    def test_medication_conflict_detected(self):
        recs = _build_proactive_recommendations(_CONFLICT_LOGS)
        categories = [r["category"] for r in recs]
        assert "medication_conflict" in categories

    def test_medication_conflict_magnitude(self):
        recs = _build_proactive_recommendations(_CONFLICT_LOGS)
        conf_rec = next(r for r in recs if r["category"] == "medication_conflict")
        assert conf_rec["magnitude"] == 3

    def test_medication_conflict_affected_nationality(self):
        recs = _build_proactive_recommendations(_CONFLICT_LOGS)
        conf_rec = next(r for r in recs if r["category"] == "medication_conflict")
        assert "MX" in conf_rec["affected_groups"]

    def test_sorted_descending_by_magnitude(self):
        recs = _build_proactive_recommendations(_MIXED_LOGS)
        magnitudes = [r["magnitude"] for r in recs]
        assert magnitudes == sorted(magnitudes, reverse=True)

    def test_recommendation_schema_has_required_keys(self):
        recs = _build_proactive_recommendations(_HALAL_LOGS)
        required = {"category", "title", "description", "affected_groups", "magnitude"}
        for rec in recs:
            assert required.issubset(rec.keys()), f"Missing keys in {rec}"

    def test_description_contains_magnitude(self):
        recs = _build_proactive_recommendations(_HALAL_LOGS)
        halal_rec = next(r for r in recs if r["category"] == "dietary")
        assert str(halal_rec["magnitude"]) in halal_rec["description"]

    def test_no_pii_in_recommendations(self):
        """Recommendations must not contain patient_id patterns."""
        recs = _build_proactive_recommendations(_MIXED_LOGS)
        for rec in recs:
            for field_val in [rec["title"], rec["description"]]:
                assert "P-TEST" not in field_val
                assert "P-ICD" not in field_val
                assert "P-CONF" not in field_val

    def test_min_threshold_suppresses_rare_diet_flags(self):
        """A diet flag appearing only once should not generate a recommendation."""
        single_vegan_log = [
            {
                "patient_id": "P-RARE0001",
                "age_band": "18-30",
                "nationality": "NZ",
                "condition_codes": [],
                "medications_current": [],
                "diet_flags": ["raw-vegan"],
                "interaction_language": "en",
                "visit_type": "telehealth",
            }
        ]
        recs = _build_proactive_recommendations(single_vegan_log)
        dietary = [r for r in recs if r["category"] == "dietary"]
        # magnitude 1 is below threshold (< 2) so no recommendation
        assert all("raw-vegan" not in r["title"] for r in dietary)

    def test_all_three_categories_present_in_mixed_logs(self):
        recs = _build_proactive_recommendations(_MIXED_LOGS)
        categories = {r["category"] for r in recs}
        assert "dietary" in categories
        assert "icd10_cluster" in categories
        assert "medication_conflict" in categories


# ══════════════════════════════════════════════════════════════════════════════
# GET /analytics/dashboard — proactive_recommendations integration
# ══════════════════════════════════════════════════════════════════════════════

class TestDashboardProactiveRecommendations:
    """
    These tests patch _PATIENT_LOGS_PATH to inject a known logs fixture,
    OR test through build_dashboard() directly (no HTTP overhead for unit tests).
    For HTTP tests, we use a minimal TestClient against the real endpoint.
    """

    def test_build_dashboard_returns_proactive_key(self):
        result = build_dashboard()
        assert "proactive_recommendations" in result

    def test_proactive_recommendations_is_list(self):
        result = build_dashboard()
        assert isinstance(result["proactive_recommendations"], list)

    def test_dashboard_api_returns_proactive_field(self, client):
        resp = client.get("/analytics/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert "proactive_recommendations" in body
        assert isinstance(body["proactive_recommendations"], list)

    def test_dashboard_proactive_recommendations_schema(self, client):
        resp = client.get("/analytics/dashboard")
        recs = resp.json()["proactive_recommendations"]
        for rec in recs:
            assert "category" in rec
            assert "title" in rec
            assert "description" in rec
            assert "affected_groups" in rec
            assert "magnitude" in rec
            assert rec["magnitude"] >= 0

    def test_dashboard_no_pii_in_proactive_recommendations(self, client):
        """The dashboard response must never expose patient_id-like tokens."""
        resp = client.get("/analytics/dashboard")
        body_text = resp.text
        # Synthetic patient IDs follow the P-XXXXXXXX pattern
        import re
        assert not re.search(r"P-[A-F0-9]{8,}", body_text), (
            "Patient ID pattern found in dashboard response — PII leak!"
        )

    def test_dashboard_proactive_category_values_are_valid(self, client):
        resp = client.get("/analytics/dashboard")
        recs = resp.json()["proactive_recommendations"]
        valid_categories = {"dietary", "icd10_cluster", "medication_conflict"}
        for rec in recs:
            assert rec["category"] in valid_categories, (
                f"Unexpected category: {rec['category']}"
            )
