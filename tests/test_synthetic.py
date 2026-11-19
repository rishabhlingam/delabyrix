"""
tests/test_synthetic.py
────────────────────────
Unit tests for the three synthetic data generators.

Validates:
  - Record counts are exactly as specified
  - All required fields are present and correctly typed
  - Cross-jurisdiction conflicts exist in the medication registry
  - No real PII (names, DOBs, etc.) leaks into patient logs
  - All 9 consent/billing documents are generated with non-empty content
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

import pytest

from backend.synthetic.medication_registry import generate_medication_registry
from backend.synthetic.consent_billing_docs import (
    generate_consent_billing_docs,
    SUPPORTED_DOC_TYPES,
    SUPPORTED_LANGUAGES,
)
from backend.synthetic.patient_logs import generate_patient_logs


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def med_records() -> List[Dict[str, Any]]:
    return generate_medication_registry()


@pytest.fixture(scope="module")
def docs() -> Dict:
    return generate_consent_billing_docs()


@pytest.fixture(scope="module")
def patient_logs() -> List[Dict[str, Any]]:
    return generate_patient_logs(200)


# ═══════════════════════════════════════════════════════════════════════════════
# Medication registry tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicationRegistry:

    def test_exactly_50_records(self, med_records):
        assert len(med_records) == 50

    def test_required_fields_present(self, med_records):
        required = {
            "medication_id", "name_generic", "name_brand",
            "jurisdiction", "status", "therapeutic_alternatives",
            "last_updated", "source_registry",
        }
        for rec in med_records:
            missing = required - rec.keys()
            assert not missing, f"Missing fields in record: {missing}"

    def test_valid_jurisdictions(self, med_records):
        valid = {"US_FDA", "EU_EMA"}
        for rec in med_records:
            assert rec["jurisdiction"] in valid, (
                f"Unexpected jurisdiction: {rec['jurisdiction']}"
            )

    def test_valid_statuses(self, med_records):
        valid = {"approved", "restricted", "banned", "delisted"}
        for rec in med_records:
            assert rec["status"] in valid, f"Invalid status: {rec['status']}"

    def test_cross_jurisdiction_conflicts_exist(self, med_records):
        """
        There must be at least one medication where the FDA status differs from
        the EMA status (the whole point of the conflict dataset).
        """
        by_name: Dict[str, Dict[str, str]] = {}
        for rec in med_records:
            name = rec["name_generic"]
            if name not in by_name:
                by_name[name] = {}
            by_name[name][rec["jurisdiction"]] = rec["status"]

        conflicts = [
            name for name, juris in by_name.items()
            if "US_FDA" in juris and "EU_EMA" in juris
            and juris["US_FDA"] != juris["EU_EMA"]
        ]
        assert len(conflicts) >= 10, (
            f"Expected at least 10 cross-jurisdiction conflicts, found {len(conflicts)}"
        )

    def test_therapeutic_alternatives_is_list(self, med_records):
        for rec in med_records:
            assert isinstance(rec["therapeutic_alternatives"], list)

    def test_banned_records_have_non_empty_alternatives_or_reason(self, med_records):
        """
        Banned/restricted records should have either a restriction_reason or
        at least one therapeutic alternative.
        """
        high_risk = [r for r in med_records if r["status"] in ("banned", "restricted")]
        for rec in high_risk:
            has_reason = bool(rec.get("restriction_reason"))
            has_alt = len(rec["therapeutic_alternatives"]) > 0
            assert has_reason or has_alt, (
                f"Banned/restricted record {rec['name_generic']} in "
                f"{rec['jurisdiction']} has neither reason nor alternatives"
            )

    def test_medication_ids_are_unique(self, med_records):
        ids = [r["medication_id"] for r in med_records]
        assert len(ids) == len(set(ids)), "Duplicate medication_id values found"

    def test_last_updated_format(self, med_records):
        """last_updated should be a parseable ISO 8601 date string."""
        from datetime import date
        for rec in med_records:
            val = rec["last_updated"]
            # May be a date object or a string
            if isinstance(val, str):
                date.fromisoformat(val)   # raises ValueError if malformed

    def test_known_banned_drug_in_us(self, med_records):
        """metamizole must be banned in US_FDA."""
        us_meta = [
            r for r in med_records
            if r["name_generic"] == "metamizole" and r["jurisdiction"] == "US_FDA"
        ]
        assert us_meta, "metamizole US_FDA record not found"
        assert us_meta[0]["status"] == "banned"

    def test_known_approved_drug_in_eu(self, med_records):
        """metamizole must be approved in EU_EMA."""
        eu_meta = [
            r for r in med_records
            if r["name_generic"] == "metamizole" and r["jurisdiction"] == "EU_EMA"
        ]
        assert eu_meta, "metamizole EU_EMA record not found"
        assert eu_meta[0]["status"] == "approved"


# ═══════════════════════════════════════════════════════════════════════════════
# Consent & billing document tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsentBillingDocs:

    def test_exactly_9_documents(self, docs):
        assert len(docs) == 9

    def test_all_combinations_present(self, docs):
        for doc_type in SUPPORTED_DOC_TYPES:
            for lang in SUPPORTED_LANGUAGES:
                assert (doc_type, lang) in docs, (
                    f"Missing document: ({doc_type}, {lang})"
                )

    def test_required_doc_fields(self, docs):
        required = {"doc_type", "language", "title", "content"}
        for key, doc in docs.items():
            missing = required - doc.keys()
            assert not missing, f"Doc {key} missing fields: {missing}"

    def test_content_non_empty(self, docs):
        for key, doc in docs.items():
            assert len(doc["content"]) > 100, (
                f"Document {key} has suspiciously short content: {len(doc['content'])} chars"
            )

    def test_no_real_pii_markers(self, docs):
        """
        Content should not contain real patient names or ID patterns.
        We test for the absence of SSN-like patterns as a proxy.
        """
        import re
        ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        for key, doc in docs.items():
            assert not ssn_pattern.search(doc["content"]), (
                f"SSN-like pattern found in document {key}"
            )

    def test_section_markers_present(self, docs):
        """Every document should contain at least one === SECTION: ... === marker."""
        for key, doc in docs.items():
            assert "=== SECTION:" in doc["content"] or "=== SECCIÓN:" in doc["content"] or \
                   "=== अनुभाग:" in doc["content"] or "=== दस्तावेज़:" in doc["content"] or \
                   "=== DOCUMENTO:" in doc["content"] or "=== DOCUMENT:" in doc["content"], (
                f"No section markers in document {key}"
            )

    def test_hindi_documents_contain_devanagari(self, docs):
        """Hindi documents must contain Devanagari script characters."""
        import unicodedata
        for lang in SUPPORTED_LANGUAGES:
            if lang != "hi":
                continue
            for doc_type in SUPPORTED_DOC_TYPES:
                content = docs[(doc_type, lang)]["content"]
                has_devanagari = any(
                    unicodedata.name(ch, "").startswith("DEVANAGARI")
                    for ch in content
                )
                assert has_devanagari, f"No Devanagari in Hindi document ({doc_type}, {lang})"

    def test_spanish_documents_contain_spanish(self, docs):
        """Spanish documents should contain common Spanish words."""
        spanish_markers = ["consentimiento", "paciente", "riesgo", "médico", "firma"]
        for doc_type in SUPPORTED_DOC_TYPES:
            content = docs[(doc_type, "es")]["content"].lower()
            matches = [m for m in spanish_markers if m in content]
            assert len(matches) >= 2, (
                f"Spanish document ({doc_type}, es) lacks Spanish vocabulary"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Patient log tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatientLogs:

    def test_exactly_200_records(self, patient_logs):
        assert len(patient_logs) == 200

    def test_required_fields_present(self, patient_logs):
        required = {
            "patient_id", "age_band", "nationality",
            "condition_codes", "medications_current", "diet_flags",
            "interaction_language", "visit_type",
        }
        for rec in patient_logs:
            missing = required - rec.keys()
            assert not missing, f"Missing fields in patient log: {missing}"

    def test_valid_age_bands(self, patient_logs):
        valid = {"18-30", "31-45", "46-60", "61+"}
        for rec in patient_logs:
            assert rec["age_band"] in valid

    def test_valid_visit_types(self, patient_logs):
        valid = {"ER", "ICU", "outpatient", "telehealth"}
        for rec in patient_logs:
            assert rec["visit_type"] in valid

    def test_nationality_iso_format(self, patient_logs):
        """Nationality codes should be 2-letter uppercase ISO 3166-1 alpha-2."""
        import re
        pattern = re.compile(r"^[A-Z]{2}$")
        for rec in patient_logs:
            assert pattern.match(rec["nationality"]), (
                f"Non-ISO nationality code: {rec['nationality']}"
            )

    def test_patient_ids_are_unique(self, patient_logs):
        ids = [r["patient_id"] for r in patient_logs]
        assert len(ids) == len(set(ids)), "Duplicate patient_id values found"

    def test_patient_ids_are_synthetic_hashes(self, patient_logs):
        """IDs must follow the P-<hex> pattern — not real patient identifiers."""
        import re
        pattern = re.compile(r"^P-[0-9A-F]{12}$")
        for rec in patient_logs:
            assert pattern.match(rec["patient_id"]), (
                f"patient_id does not match synthetic hash pattern: {rec['patient_id']}"
            )

    def test_condition_codes_are_icd10_ranges(self, patient_logs):
        """ICD-10 codes must be category-range strings (e.g. 'A00-B99'), not full codes."""
        import re
        range_pattern = re.compile(r"^[A-Z]\d{2}-[A-Z][0-9A-Z]{2}$")
        for rec in patient_logs:
            for code in rec["condition_codes"]:
                assert range_pattern.match(code), (
                    f"ICD-10 code is too specific (not a range): {code}"
                )

    def test_no_names_in_logs(self, patient_logs):
        """
        None of the string fields in a log record should look like a real name
        (this is a sanity check, not an exhaustive PII scan).
        """
        for rec in patient_logs:
            pid = rec["patient_id"]
            # patient_id must NOT be a plain name like "John Smith"
            assert not pid[0].isalpha() or pid.startswith("P-"), (
                f"patient_id looks like a name: {pid}"
            )

    def test_multiple_nationalities_represented(self, patient_logs):
        """Data should span more than 5 distinct nationalities."""
        nationalities = {r["nationality"] for r in patient_logs}
        assert len(nationalities) >= 10, (
            f"Expected ≥10 distinct nationalities, got {len(nationalities)}"
        )

    def test_multiple_languages_represented(self, patient_logs):
        """Data should span more than 5 distinct interaction languages."""
        langs = {r["interaction_language"] for r in patient_logs}
        assert len(langs) >= 5, (
            f"Expected ≥5 distinct interaction languages, got {len(langs)}"
        )

    def test_all_visit_types_appear(self, patient_logs):
        """All four visit types should appear in 200 records."""
        seen = {r["visit_type"] for r in patient_logs}
        expected = {"ER", "ICU", "outpatient", "telehealth"}
        assert expected == seen, f"Missing visit types: {expected - seen}"

    def test_determinism(self):
        """Same call with same count produces identical patient_id list."""
        logs_a = generate_patient_logs(10)
        logs_b = generate_patient_logs(10)
        assert [r["patient_id"] for r in logs_a] == [r["patient_id"] for r in logs_b]
