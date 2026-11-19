"""
tests/test_registry.py
────────────────────────
Unit tests for Phase 2 modules:
  - backend/jurisdiction/rules.py
  - backend/jurisdiction/resolver.py
  - backend/registry/models.py
  - backend/registry/query.py
  - backend/registry/sync.py

All registry tests use sync.inject_registry() to bypass filesystem I/O,
injecting the synthetic data directly from the generator.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from backend.jurisdiction.rules import (
    get_rule,
    is_known_country,
    FALLBACK_RULE,
    JURISDICTION_RULES,
)
from backend.jurisdiction.resolver import resolve, JurisdictionContext
from backend.registry.models import (
    MedicationRecord,
    MedicationStatus,
    Jurisdiction,
    RegistryListResponse,
)
from backend.registry.sync import inject_registry, get_registry, last_sync_time
from backend.registry.query import (
    check_medication,
    list_medications,
    get_medication_by_id,
    find_cross_jurisdiction_conflicts,
)
from backend.synthetic.medication_registry import generate_medication_registry


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def load_registry():
    """Inject synthetic registry into the in-memory cache before each test."""
    inject_registry(generate_medication_registry())
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# Jurisdiction rules tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestJurisdictionRules:

    def test_us_uses_fda(self):
        rule = get_rule("US")
        assert rule["registry"] == "US_FDA"

    def test_us_uses_hipaa(self):
        rule = get_rule("US")
        assert rule["privacy_law"] == "HIPAA"

    def test_de_uses_ema(self):
        rule = get_rule("DE")
        assert rule["registry"] == "EU_EMA"

    def test_de_uses_gdpr(self):
        rule = get_rule("DE")
        assert rule["privacy_law"] == "GDPR"

    def test_case_insensitive(self):
        assert get_rule("us") == get_rule("US")
        assert get_rule("de") == get_rule("DE")

    def test_unknown_country_returns_fallback(self):
        rule = get_rule("ZZ")
        assert rule == FALLBACK_RULE
        assert rule["registry"] == "OTHER"

    def test_is_known_country_true(self):
        assert is_known_country("US")
        assert is_known_country("DE")
        assert is_known_country("IN")

    def test_is_known_country_false(self):
        assert not is_known_country("ZZ")
        assert not is_known_country("XX")

    def test_all_eu_members_use_ema(self):
        """All EU member states in the table must map to EU_EMA."""
        eu_members = [
            "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI",
            "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
            "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
        ]
        for code in eu_members:
            rule = get_rule(code)
            assert rule["registry"] == "EU_EMA", (
                f"{code} should use EU_EMA, got {rule['registry']}"
            )

    def test_all_eu_members_use_gdpr(self):
        eu_members = ["FR", "DE", "IT", "ES", "NL", "PL"]
        for code in eu_members:
            rule = get_rule(code)
            assert rule["privacy_law"] == "GDPR"

    def test_all_rules_have_required_keys(self):
        required = {"country_name", "registry", "privacy_law", "cultural_norms", "region"}
        for code, rule in JURISDICTION_RULES.items():
            missing = required - rule.keys()
            assert not missing, f"Rule for {code} missing keys: {missing}"

    def test_in_uses_south_asian_norms(self):
        rule = get_rule("IN")
        assert rule["cultural_norms"] == "south_asian"


# ═══════════════════════════════════════════════════════════════════════════════
# Jurisdiction resolver tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestJurisdictionResolver:

    def test_returns_jurisdiction_context(self):
        ctx = resolve("US")
        assert isinstance(ctx, JurisdictionContext)

    def test_us_context_uses_fda(self):
        ctx = resolve("US")
        assert ctx.registry == "US_FDA"
        assert ctx.uses_fda is True
        assert ctx.uses_ema is False

    def test_de_context_uses_ema(self):
        ctx = resolve("DE")
        assert ctx.registry == "EU_EMA"
        assert ctx.uses_ema is True
        assert ctx.uses_fda is False

    def test_us_requires_hipaa(self):
        ctx = resolve("US")
        assert ctx.requires_hipaa is True
        assert ctx.requires_gdpr is False

    def test_de_requires_gdpr(self):
        ctx = resolve("DE")
        assert ctx.requires_gdpr is True
        assert ctx.requires_hipaa is False

    def test_unknown_country_is_ambiguous(self):
        ctx = resolve("ZZ")
        assert ctx.is_ambiguous is True
        assert ctx.registry == "OTHER"

    def test_known_country_not_ambiguous(self):
        ctx = resolve("FR")
        assert ctx.is_ambiguous is False

    def test_case_insensitive_resolve(self):
        ctx_lower = resolve("de")
        ctx_upper = resolve("DE")
        assert ctx_lower.registry == ctx_upper.registry
        assert ctx_lower.privacy_law == ctx_upper.privacy_law

    def test_empty_string_is_ambiguous(self):
        ctx = resolve("")
        assert ctx.is_ambiguous is True

    def test_to_dict_returns_all_keys(self):
        ctx = resolve("US")
        d = ctx.to_dict()
        expected_keys = {
            "country_code", "country_name", "registry",
            "privacy_law", "cultural_norms", "region", "is_ambiguous",
        }
        assert expected_keys == set(d.keys())

    def test_frozen_dataclass(self):
        """JurisdictionContext must be immutable."""
        ctx = resolve("US")
        with pytest.raises((AttributeError, TypeError)):
            ctx.registry = "MUTATED"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════════
# Registry models tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistryModels:

    def test_medication_record_validates_from_dict(self):
        raw = generate_medication_registry()[0]
        record = MedicationRecord.model_validate(raw)
        assert record.medication_id == raw["medication_id"]

    def test_enum_values_are_strings(self):
        """With use_enum_values=True, attributes should be plain strings."""
        raw = generate_medication_registry()[0]
        record = MedicationRecord.model_validate(raw)
        assert isinstance(record.jurisdiction, str)
        assert isinstance(record.status, str)

    def test_invalid_status_raises(self):
        from pydantic import ValidationError
        raw = {**generate_medication_registry()[0], "status": "not_a_status"}
        with pytest.raises(ValidationError):
            MedicationRecord.model_validate(raw)

    def test_invalid_jurisdiction_raises(self):
        from pydantic import ValidationError
        raw = {**generate_medication_registry()[0], "jurisdiction": "MARS_REG"}
        with pytest.raises(ValidationError):
            MedicationRecord.model_validate(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# Registry sync tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistrySync:

    def test_inject_and_get(self):
        inject_registry(generate_medication_registry())
        records = get_registry(auto_load=False)
        assert len(records) == 50

    def test_inject_updates_last_sync(self):
        from datetime import datetime
        inject_registry(generate_medication_registry())
        ts = last_sync_time()
        assert isinstance(ts, datetime)

    def test_get_registry_returns_copy(self):
        """Mutating the returned list must not affect the internal cache."""
        inject_registry(generate_medication_registry())
        a = get_registry(auto_load=False)
        a.clear()
        b = get_registry(auto_load=False)
        assert len(b) == 50

    def test_empty_cache_no_autoload(self):
        inject_registry([])
        records = get_registry(auto_load=False)
        assert records == []

    def test_file_not_found_raises(self):
        from pathlib import Path
        from backend.registry.sync import _load_from_file
        with pytest.raises(FileNotFoundError):
            _load_from_file(Path("/nonexistent/path/registry.json"))


# ═══════════════════════════════════════════════════════════════════════════════
# Registry query tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistryQuery:

    def test_check_known_medication_fda(self):
        result = check_medication("metamizole", "US_FDA")
        assert result is not None
        assert result.name_generic == "metamizole"
        assert result.jurisdiction == "US_FDA"
        assert result.status == "banned"

    def test_check_known_medication_ema(self):
        result = check_medication("metamizole", "EU_EMA")
        assert result is not None
        assert result.status == "approved"

    def test_check_by_brand_name(self):
        result = check_medication("Dipyrone", "US_FDA")
        assert result is not None
        assert result.name_generic == "metamizole"

    def test_check_case_insensitive(self):
        result_lower = check_medication("METAMIZOLE", "US_FDA")
        result_upper = check_medication("metamizole", "US_FDA")
        assert result_lower is not None
        assert result_upper is not None
        assert result_lower.medication_id == result_upper.medication_id

    def test_check_unknown_medication_returns_none(self):
        result = check_medication("fictional_drug_xyz", "US_FDA")
        assert result is None

    def test_list_all_no_filter(self):
        response = list_medications(page=1, page_size=100)
        assert isinstance(response, RegistryListResponse)
        assert response.total == 50
        assert len(response.records) == 50

    def test_list_fda_only(self):
        response = list_medications(jurisdiction="US_FDA", page_size=100)
        assert response.total == 25
        for r in response.records:
            assert r.jurisdiction == "US_FDA"

    def test_list_ema_only(self):
        response = list_medications(jurisdiction="EU_EMA", page_size=100)
        assert response.total == 25
        for r in response.records:
            assert r.jurisdiction == "EU_EMA"

    def test_pagination(self):
        page1 = list_medications(page=1, page_size=10)
        page2 = list_medications(page=2, page_size=10)
        assert len(page1.records) == 10
        assert len(page2.records) == 10
        ids1 = {r.medication_id for r in page1.records}
        ids2 = {r.medication_id for r in page2.records}
        assert ids1.isdisjoint(ids2), "Pages should not overlap"

    def test_pagination_last_page(self):
        response = list_medications(page=3, page_size=20)
        assert response.total == 50
        assert len(response.records) == 10   # 50 records, page 3 of 20 = last 10

    def test_get_by_id(self):
        records = get_registry(auto_load=False)
        target_id = records[0]["medication_id"]
        record = get_medication_by_id(target_id)
        assert record is not None
        assert record.medication_id == target_id

    def test_get_by_id_not_found(self):
        record = get_medication_by_id("00000000-0000-0000-0000-000000000000")
        assert record is None

    def test_cross_jurisdiction_conflicts_metamizole(self):
        conflicts = find_cross_jurisdiction_conflicts("metamizole")
        assert len(conflicts) == 2
        jurisdictions = {r.jurisdiction for r in conflicts}
        assert "US_FDA" in jurisdictions
        assert "EU_EMA" in jurisdictions

    def test_cross_jurisdiction_different_statuses(self):
        """metamizole must have different statuses in FDA vs EMA."""
        conflicts = find_cross_jurisdiction_conflicts("metamizole")
        statuses = {r.jurisdiction: r.status for r in conflicts}
        assert statuses["US_FDA"] != statuses["EU_EMA"]

    def test_list_page_size_capped_at_100(self):
        response = list_medications(page=1, page_size=999)
        assert len(response.records) <= 100

    def test_list_page_1_returns_first_records(self):
        all_response = list_medications(page=1, page_size=50)
        page1 = list_medications(page=1, page_size=5)
        assert page1.records[0].medication_id == all_response.records[0].medication_id
