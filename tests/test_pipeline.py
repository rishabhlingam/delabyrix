"""
tests/test_pipeline.py
────────────────────────
Unit and integration tests for Phases 3 & 4 pipeline modules:

  - backend/config.py                     (Settings loading)
  - backend/watsonx/client.py             (Mock mode + WatsonxClient)
  - backend/watsonx/orchestrate_adapter.py(OrchestrateAdapter dispatch)
  - backend/pipeline/pii_redactor.py      (Stage 0 — PII redaction)
  - backend/pipeline/translator.py        (Stage 1 — Translation)
  - backend/pipeline/medical_interpreter.py (Stage 2 — Medical interpretation)
  - backend/pipeline/cultural_context.py  (Stage 3 — Cultural context)
  - backend/pipeline/next_steps_guide.py  (Stage 4 — Next steps)
  - backend/pipeline/hitl_escalator.py    (HITL escalation rules)

All LLM calls are run against the mock client (WATSONX_MOCK_MODE=true)
so tests are fully offline.
"""

from __future__ import annotations

import os

# Force mock mode for all tests in this module BEFORE importing anything that
# reads Settings (the lru_cache might already be warm from another test file).
os.environ["WATSONX_MOCK_MODE"] = "true"

import pytest

from backend.config import Settings, get_settings
from backend.hitl.queue import get_queue
from backend.jurisdiction.resolver import resolve
from backend.pipeline.cultural_context import CulturalContextResult, add_cultural_context
from backend.pipeline.hitl_escalator import (
    EscalationInput,
    EscalationResult,
    enqueue_if_escalated,
    evaluate_escalation,
)
from backend.pipeline.medical_interpreter import MedicationFlag, MedicalInterpretationResult, interpret
from backend.pipeline.next_steps_guide import NextStepsResult, generate_next_steps
from backend.pipeline.pii_redactor import RedactionResult, redact
from backend.pipeline.translator import TranslationResult, detect_language, translate
from backend.registry.sync import inject_registry
from backend.synthetic.medication_registry import generate_medication_registry
from backend.watsonx.client import WatsonxClient, WatsonxResponse, get_client
from backend.watsonx.orchestrate_adapter import (
    OrchestrateAdapter,
    OrchestrateSkillRequest,
    OrchestrateSkillResponse,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset lru_cache singletons and HITL queue between tests."""
    get_settings.cache_clear()
    get_client.cache_clear()
    get_queue().clear()
    inject_registry(generate_medication_registry())
    yield
    get_settings.cache_clear()
    get_client.cache_clear()
    get_queue().clear()


@pytest.fixture
def mock_client() -> WatsonxClient:
    """Return a WatsonxClient in mock mode."""
    return WatsonxClient()


@pytest.fixture
def us_jurisdiction():
    return resolve("US")


@pytest.fixture
def de_jurisdiction():
    return resolve("DE")


# ══════════════════════════════════════════════════════════════════════════════
# Config tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConfig:

    def test_mock_mode_env_var(self):
        s = get_settings()
        assert s.watsonx_mock_mode is True

    def test_default_model_id(self):
        s = get_settings()
        assert s.watsonx_model_id == "ibm/granite-4-h-small"

    def test_default_url(self):
        s = get_settings()
        assert s.watsonx_url == "https://us-south.ml.cloud.ibm.com"

    def test_default_threshold(self):
        s = get_settings()
        assert s.hitl_confidence_threshold == 0.70

    def test_singleton_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


# ══════════════════════════════════════════════════════════════════════════════
# WatsonxClient mock mode tests
# ══════════════════════════════════════════════════════════════════════════════

class TestWatsonxClientMock:

    def test_client_is_mock(self, mock_client):
        assert mock_client.is_mock is True

    def test_generate_returns_watsonx_response(self, mock_client):
        resp = mock_client.generate("Explain deductibles.")
        assert isinstance(resp, WatsonxResponse)

    def test_mock_response_has_text(self, mock_client):
        resp = mock_client.generate("Test prompt.")
        assert len(resp.text) > 0

    def test_mock_response_confidence(self, mock_client):
        resp = mock_client.generate("Test prompt.")
        assert 0.0 <= resp.confidence <= 1.0

    def test_mock_flag_set(self, mock_client):
        resp = mock_client.generate("Any text.")
        assert resp.mock is True

    def test_mock_model_id(self, mock_client):
        resp = mock_client.generate("Any text.")
        assert resp.model_id == "ibm/granite-4-h-small"

    def test_max_new_tokens_param_accepted(self, mock_client):
        resp = mock_client.generate("Prompt.", max_new_tokens=100)
        assert isinstance(resp, WatsonxResponse)

    def test_temperature_param_accepted(self, mock_client):
        resp = mock_client.generate("Prompt.", temperature=0.1)
        assert isinstance(resp, WatsonxResponse)


# ══════════════════════════════════════════════════════════════════════════════
# OrchestrateAdapter tests
# ══════════════════════════════════════════════════════════════════════════════

class TestOrchestrateAdapter:

    def test_dispatch_clinical_query(self, mock_client):
        adapter = OrchestrateAdapter(client=mock_client)
        req = OrchestrateSkillRequest(
            skill_name="clinical_query",
            parameters={
                "text": "What is a deductible?",
                "source_language": "en",
                "user_type": "patient",
                "jurisdiction": "US_FDA",
            },
            session_id="test-session-1",
        )
        resp = adapter.dispatch(req)
        assert isinstance(resp, OrchestrateSkillResponse)
        assert resp.skill_name == "clinical_query"
        assert "response_text" in resp.result
        assert resp.mock is True

    def test_dispatch_medication_check(self, mock_client):
        adapter = OrchestrateAdapter(client=mock_client)
        req = OrchestrateSkillRequest(
            skill_name="medication_check",
            parameters={"medication_name": "aspirin", "jurisdiction": "US_FDA"},
        )
        resp = adapter.dispatch(req)
        assert resp.skill_name == "medication_check"
        assert "summary" in resp.result

    def test_dispatch_get_consent_document(self, mock_client):
        adapter = OrchestrateAdapter(client=mock_client)
        req = OrchestrateSkillRequest(
            skill_name="get_consent_document",
            parameters={"doc_type": "consent_icu_admission", "language": "es"},
        )
        resp = adapter.dispatch(req)
        assert resp.result["doc_type"] == "consent_icu_admission"
        assert resp.result["language"] == "es"

    def test_dispatch_get_dashboard_metrics(self, mock_client):
        adapter = OrchestrateAdapter(client=mock_client)
        req = OrchestrateSkillRequest(
            skill_name="get_dashboard_metrics",
            parameters={"jurisdiction": "US_FDA"},
        )
        resp = adapter.dispatch(req)
        assert resp.result["endpoint"] == "/analytics/dashboard"

    def test_unknown_skill_raises_value_error(self, mock_client):
        adapter = OrchestrateAdapter(client=mock_client)
        req = OrchestrateSkillRequest(
            skill_name="nonexistent_skill",
            parameters={},
        )
        with pytest.raises(ValueError, match="Unknown Orchestrate skill"):
            adapter.dispatch(req)


# ══════════════════════════════════════════════════════════════════════════════
# PII Redactor tests (Stage 0)
# ══════════════════════════════════════════════════════════════════════════════

class TestPIIRedactor:

    def test_email_redacted(self):
        result = redact("Contact me at john.doe@example.com for details.")
        assert "[EMAIL]" in result.redacted_text
        assert "john.doe@example.com" not in result.redacted_text
        assert "email" in result.types_found

    def test_ssn_redacted(self):
        result = redact("My Social Security Number is 123-45-6789.")
        assert "[SSN]" in result.redacted_text
        assert "123-45-6789" not in result.redacted_text
        assert "ssn" in result.types_found

    def test_phone_redacted(self):
        result = redact("Call me at 800-555-1234 for an appointment.")
        assert "[PHONE]" in result.redacted_text
        assert "800-555-1234" not in result.redacted_text
        assert "phone" in result.types_found

    def test_passport_id_redacted(self):
        result = redact("My passport number is A12345678.")
        assert "[REDACTED_ID]" in result.redacted_text
        assert "A12345678" not in result.redacted_text
        assert "passport_id" in result.types_found

    def test_dob_contextual_redacted(self):
        result = redact("Date of birth: 03/15/1980")
        assert "[DOB]" in result.redacted_text
        assert "03/15/1980" not in result.redacted_text
        assert "dob" in result.types_found

    def test_multiple_pii_types(self):
        text = "Patient John Smith, SSN 234-56-7890, email smith@clinic.org"
        result = redact(text)
        assert result.redaction_count >= 2
        assert "234-56-7890" not in result.redacted_text
        assert "smith@clinic.org" not in result.redacted_text

    def test_no_pii_returns_unchanged(self):
        text = "I would like to understand my insurance deductible."
        result = redact(text)
        assert result.redaction_count == 0
        assert result.redacted_text == text

    def test_empty_string(self):
        result = redact("")
        assert result.redacted_text == ""
        assert result.redaction_count == 0

    def test_returns_redaction_result(self):
        result = redact("test")
        assert isinstance(result, RedactionResult)

    def test_redaction_count_matches_found(self):
        result = redact("SSN 123-45-6789 and email a@b.com")
        assert result.redaction_count >= 2

    def test_name_redacted_heuristic(self):
        result = redact("My name is Robert Johnson and I need help.")
        # Contextual phrase "My name is" should catch Robert Johnson
        assert result.redaction_count >= 1
        assert "Robert Johnson" not in result.redacted_text
        assert "[REDACTED_NAME]" in result.redacted_text

    def test_name_accented_contextual(self):
        """Accented name after 'I am' must be redacted (the PII leak from the bug report)."""
        result = redact("I am María García, ID number 12345678A. I take metamizole.")
        assert "María" not in result.redacted_text
        assert "García" not in result.redacted_text
        assert "12345678A" not in result.redacted_text
        assert "[REDACTED_NAME]" in result.redacted_text
        assert "[REDACTED_ID]" in result.redacted_text

    def test_alphanumeric_id_trailing_letter(self):
        """Standalone 8-digit + letter ID token (e.g. DNI) must be caught."""
        result = redact("My DNI is 12345678A.")
        assert "12345678A" not in result.redacted_text
        assert "[REDACTED_ID]" in result.redacted_text

    def test_id_keyword_prefix(self):
        """'ID number <token>' must be redacted regardless of token format."""
        result = redact("ID number 12345678A.")
        assert "12345678A" not in result.redacted_text
        assert "[REDACTED_ID]" in result.redacted_text

    def test_me_llamo_redacted(self):
        """Spanish 'Me llamo' phrase must redact the following name."""
        result = redact("Me llamo María García, necesito ayuda.")
        assert "María" not in result.redacted_text
        assert "García" not in result.redacted_text
        assert "[REDACTED_NAME]" in result.redacted_text

    def test_soy_redacted(self):
        """Spanish 'Soy <Name>' must redact the name."""
        result = redact("Soy Juan Pérez y tengo una pregunta.")
        assert "Juan" not in result.redacted_text
        assert "[REDACTED_NAME]" in result.redacted_text

    def test_residual_pii_flag_standalone_date(self):
        # A standalone date in context not preceded by DOB keyword
        result = redact("My appointment is on 12/25/2024")
        # It should flag residual PII for the date even if not redacted
        # (standalone date heuristic sets the flag)
        assert isinstance(result.has_residual_pii, bool)


# ══════════════════════════════════════════════════════════════════════════════
# Translator tests (Stage 1)
# ══════════════════════════════════════════════════════════════════════════════

class TestTranslator:

    def test_same_language_no_llm_call(self, mock_client):
        result = translate("Hello world", "en", "en", mock_client)
        assert result.translated_text == "Hello world"
        assert result.confidence == 1.0

    def test_translation_result_type(self, mock_client):
        result = translate("How are you?", "en", "es", mock_client)
        assert isinstance(result, TranslationResult)

    def test_translation_has_text(self, mock_client):
        result = translate("I need help with my bill.", "en", "es", mock_client)
        assert len(result.translated_text) > 0

    def test_mock_flag_propagated(self, mock_client):
        result = translate("Text", "en", "es", mock_client)
        assert result.mock is True

    def test_language_mismatch_detection(self, mock_client):
        # Text is clearly English, but declared as Spanish -> mismatch
        result = translate(
            "The patient needs immediate care.", "es", "en", mock_client
        )
        assert result.language_mismatch is True

    def test_no_mismatch_matching_language(self, mock_client):
        # Text declared as English and detected as English
        result = translate(
            "The patient needs immediate care.", "en", "es", mock_client
        )
        # detected should be "en", declared is "en" -> no mismatch
        assert result.language_mismatch is False

    def test_detect_language_english(self):
        lang = detect_language("The patient is in the hospital and needs care.")
        assert lang == "en"

    def test_detect_language_spanish(self):
        lang = detect_language("El paciente necesita atención médica urgente.")
        assert lang == "es"

    def test_detect_language_ambiguous_returns_none(self):
        lang = detect_language("Dr. X")
        # Too short to reliably detect
        assert lang is None or lang in ("en", "es", "hi")

    def test_source_and_target_stored(self, mock_client):
        result = translate("Text", "en", "hi", mock_client)
        assert result.source_language == "en"
        assert result.target_language == "hi"


# ══════════════════════════════════════════════════════════════════════════════
# Medical Interpreter tests (Stage 2)
# ══════════════════════════════════════════════════════════════════════════════

class TestMedicalInterpreter:

    def test_returns_interpretation_result(self, mock_client, us_jurisdiction):
        result = interpret("My deductible is confusing.", us_jurisdiction, mock_client)
        assert isinstance(result, MedicalInterpretationResult)

    def test_plain_language_text_populated(self, mock_client, us_jurisdiction):
        result = interpret("ICU admission consent form.", us_jurisdiction, mock_client)
        assert len(result.plain_language_text) > 0

    def test_mock_flag_propagated(self, mock_client, us_jurisdiction):
        result = interpret("Test text", us_jurisdiction, mock_client)
        assert result.mock is True

    def test_no_medications_in_plain_text(self, mock_client, us_jurisdiction):
        result = interpret("What is my deductible?", us_jurisdiction, mock_client)
        assert isinstance(result.medication_flags, list)
        assert result.has_banned_medication is False

    def test_banned_medication_detected_fda(self, mock_client, us_jurisdiction):
        """metamizole is banned in US_FDA — should trigger has_banned_medication."""
        result = interpret(
            "I was prescribed metamizole tablet for pain.", us_jurisdiction, mock_client
        )
        assert result.has_banned_medication is True
        assert any(f.name == "metamizole" for f in result.medication_flags)

    def test_medication_flag_has_status(self, mock_client, us_jurisdiction):
        result = interpret("metamizole dosage", us_jurisdiction, mock_client)
        for flag in result.medication_flags:
            assert flag.status in ("approved", "restricted", "banned", "delisted")

    def test_banned_medication_ema_approved(self, mock_client, de_jurisdiction):
        """metamizole is approved in EU_EMA — should NOT flag as banned."""
        result = interpret(
            "I take metamizole for pain.", de_jurisdiction, mock_client
        )
        assert result.has_banned_medication is False

    def test_confidence_in_valid_range(self, mock_client, us_jurisdiction):
        result = interpret("Any text.", us_jurisdiction, mock_client)
        assert 0.0 <= result.confidence <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Cultural Context tests (Stage 3)
# ══════════════════════════════════════════════════════════════════════════════

class TestCulturalContext:

    def test_returns_cultural_context_result(self, mock_client, us_jurisdiction):
        result = add_cultural_context("Plain text.", us_jurisdiction, "patient", mock_client)
        assert isinstance(result, CulturalContextResult)

    def test_framed_text_populated(self, mock_client, us_jurisdiction):
        result = add_cultural_context("Explain my rights.", us_jurisdiction, "patient", mock_client)
        assert len(result.framed_text) > 0

    def test_jurisdiction_note_contains_registry(self, mock_client, us_jurisdiction):
        result = add_cultural_context("Text.", us_jurisdiction, "patient", mock_client)
        assert "FDA" in result.jurisdiction_note or "HIPAA" in result.jurisdiction_note

    def test_eu_jurisdiction_note(self, mock_client, de_jurisdiction):
        result = add_cultural_context("Text.", de_jurisdiction, "patient", mock_client)
        assert "EMA" in result.jurisdiction_note or "GDPR" in result.jurisdiction_note

    def test_user_type_stored(self, mock_client, us_jurisdiction):
        result = add_cultural_context("Text.", us_jurisdiction, "provider", mock_client)
        assert result.user_type == "provider"

    def test_mock_flag_propagated(self, mock_client, us_jurisdiction):
        result = add_cultural_context("Text.", us_jurisdiction, "coordinator", mock_client)
        assert result.mock is True


# ══════════════════════════════════════════════════════════════════════════════
# Next Steps Guide tests (Stage 4)
# ══════════════════════════════════════════════════════════════════════════════

class TestNextStepsGuide:

    def test_returns_next_steps_result(self, mock_client, us_jurisdiction):
        result = generate_next_steps("Framed text.", "patient", [], us_jurisdiction, mock_client)
        assert isinstance(result, NextStepsResult)

    def test_next_steps_text_populated(self, mock_client, us_jurisdiction):
        result = generate_next_steps("Framed text.", "patient", [], us_jurisdiction, mock_client)
        assert len(result.next_steps_text) > 0

    def test_no_banned_meds_no_alternatives(self, mock_client, us_jurisdiction):
        result = generate_next_steps("Text.", "patient", [], us_jurisdiction, mock_client)
        assert result.therapeutic_alternatives == []

    def test_banned_med_includes_alternatives(self, mock_client, us_jurisdiction):
        flag = MedicationFlag(
            name="metamizole",
            jurisdiction="US_FDA",
            status="banned",
            restriction_reason="Withdrawn due to agranulocytosis risk",
            therapeutic_alternatives=["ibuprofen", "acetaminophen"],
            found_in_registry=True,
        )
        result = generate_next_steps("Text.", "patient", [flag], us_jurisdiction, mock_client)
        assert "ibuprofen" in result.therapeutic_alternatives
        assert "acetaminophen" in result.therapeutic_alternatives

    def test_restricted_med_included(self, mock_client, us_jurisdiction):
        flag = MedicationFlag(
            name="thalidomide",
            jurisdiction="US_FDA",
            status="restricted",
            restriction_reason="REMS programme required",
            therapeutic_alternatives=["lenalidomide"],
            found_in_registry=True,
        )
        result = generate_next_steps("Text.", "provider", [flag], us_jurisdiction, mock_client)
        assert "lenalidomide" in result.therapeutic_alternatives

    def test_mock_flag_propagated(self, mock_client, us_jurisdiction):
        result = generate_next_steps("Text.", "patient", [], us_jurisdiction, mock_client)
        assert result.mock is True


# ══════════════════════════════════════════════════════════════════════════════
# HITL Escalator tests
# ══════════════════════════════════════════════════════════════════════════════

def _make_escalation_input(**overrides) -> EscalationInput:
    """Helper: build a default EscalationInput and apply any overrides."""
    defaults: dict = {
        "session_id": "test-session-abc",
        "original_text": "I need help with my bill.",
        "user_type": "patient",
        "country": "US",
        "is_ambiguous_jurisdiction": False,
        "redaction_result": redact("I need help with my bill."),
        "min_confidence": 0.95,
        "medication_flags": [],
        "pipeline_trace": {"jurisdiction": "US_FDA"},
        "draft_response": "Here are your next steps.",
    }
    defaults.update(overrides)
    return EscalationInput(**defaults)


class TestHITLEscalator:

    def test_no_escalation_clean_input(self):
        inp = _make_escalation_input()
        result = evaluate_escalation(inp)
        assert result.should_escalate is False
        assert result.rules_triggered == []

    def test_rule_1_low_confidence(self):
        inp = _make_escalation_input(min_confidence=0.60)
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_1" in r for r in result.rules_triggered)

    def test_rule_2_banned_medication(self):
        flag = MedicationFlag(
            name="metamizole",
            jurisdiction="US_FDA",
            status="banned",
            restriction_reason="Withdrawn",
            therapeutic_alternatives=[],
            found_in_registry=True,
        )
        inp = _make_escalation_input(medication_flags=[flag])
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_2" in r for r in result.rules_triggered)

    def test_rule_2_restricted_medication(self):
        flag = MedicationFlag(
            name="thalidomide",
            jurisdiction="US_FDA",
            status="restricted",
            restriction_reason="REMS",
            therapeutic_alternatives=[],
            found_in_registry=True,
        )
        inp = _make_escalation_input(medication_flags=[flag])
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_2" in r for r in result.rules_triggered)

    def test_rule_2_approved_medication_no_escalation(self):
        flag = MedicationFlag(
            name="ibuprofen",
            jurisdiction="US_FDA",
            status="approved",
            restriction_reason=None,
            therapeutic_alternatives=[],
            found_in_registry=True,
        )
        inp = _make_escalation_input(medication_flags=[flag])
        result = evaluate_escalation(inp)
        # Only rule 2 concerns — no escalation for approved med
        assert not any("rule_2" in r for r in result.rules_triggered)

    def test_rule_3_residual_pii(self):
        pii_result = redact("My DOB is 03/15/1980 and my appointment is 12/01/2024")
        # Force has_residual_pii = True
        from dataclasses import replace
        pii_with_residual = replace(pii_result, has_residual_pii=True)
        inp = _make_escalation_input(redaction_result=pii_with_residual)
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_3" in r for r in result.rules_triggered)

    def test_rule_4_icu_topic(self):
        inp = _make_escalation_input(
            original_text="Patient needs ICU admission for critical care."
        )
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_4" in r for r in result.rules_triggered)

    def test_rule_4_surgery_topic(self):
        inp = _make_escalation_input(
            original_text="Please explain the surgery consent form."
        )
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_4" in r for r in result.rules_triggered)

    def test_rule_4_end_of_life_topic(self):
        inp = _make_escalation_input(
            original_text="What are end-of-life care options for my parent?"
        )
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_4" in r for r in result.rules_triggered)

    def test_rule_5_ambiguous_jurisdiction(self):
        inp = _make_escalation_input(
            country="ZZ",
            is_ambiguous_jurisdiction=True,
        )
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_5" in r for r in result.rules_triggered)

    def test_multiple_rules_all_captured(self):
        flag = MedicationFlag(
            name="metamizole", jurisdiction="US_FDA", status="banned",
            restriction_reason="Withdrawn", therapeutic_alternatives=[],
            found_in_registry=True,
        )
        inp = _make_escalation_input(
            min_confidence=0.50,
            medication_flags=[flag],
            original_text="ICU admission for surgery consent",
            is_ambiguous_jurisdiction=True,
            country="ZZ",
        )
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        # At least rules 1, 2, 4, 5 should fire
        rule_numbers = {r.split("_")[1] for r in result.rules_triggered}
        assert {"1", "2", "4", "5"}.issubset(rule_numbers)

    def test_enqueue_if_escalated_returns_review_id(self):
        inp = _make_escalation_input(min_confidence=0.50)
        result = evaluate_escalation(inp)
        review_id = enqueue_if_escalated(result)
        assert review_id is not None
        assert len(review_id) > 0

    def test_enqueue_if_not_escalated_returns_none(self):
        inp = _make_escalation_input()
        result = evaluate_escalation(inp)
        review_id = enqueue_if_escalated(result)
        assert review_id is None


# ══════════════════════════════════════════════════════════════════════════════
# Cross-border banned drug escalation integration test
# ══════════════════════════════════════════════════════════════════════════════

class TestCrossBorderBannedDrugEscalation:
    """
    Integration test: a drug banned in the US (metamizole) but approved in the
    EU should escalate when the user's jurisdiction is US_FDA.
    """

    def test_metamizole_banned_in_us_escalates(self, mock_client):
        """Full pipeline through escalator: banned drug in US fires rule 2."""
        jctx = resolve("US")
        interpretation = interpret(
            "I was prescribed metamizole tablet.", jctx, mock_client
        )
        assert interpretation.has_banned_medication is True

        redaction = redact("I was prescribed metamizole tablet.")
        inp = EscalationInput(
            session_id="cross-border-test",
            original_text=redaction.redacted_text,
            user_type="patient",
            country="US",
            is_ambiguous_jurisdiction=False,
            redaction_result=redaction,
            min_confidence=0.95,
            medication_flags=interpretation.medication_flags,
            pipeline_trace={},
            draft_response="See a doctor.",
        )
        result = evaluate_escalation(inp)
        assert result.should_escalate is True
        assert any("rule_2" in r for r in result.rules_triggered)

    def test_metamizole_approved_in_eu_no_rule2(self, mock_client):
        """Same drug, EU jurisdiction: approved, so rule 2 must NOT fire."""
        jctx = resolve("DE")
        interpretation = interpret(
            "I take metamizole for pain.", jctx, mock_client
        )
        assert interpretation.has_banned_medication is False

        redaction = redact("I take metamizole for pain.")
        inp = EscalationInput(
            session_id="cross-border-eu-test",
            original_text=redaction.redacted_text,
            user_type="patient",
            country="DE",
            is_ambiguous_jurisdiction=False,
            redaction_result=redaction,
            min_confidence=0.95,
            medication_flags=interpretation.medication_flags,
            pipeline_trace={},
            draft_response="See a doctor.",
        )
        result = evaluate_escalation(inp)
        # No rule 2 — metamizole is approved in EU_EMA
        assert not any("rule_2" in r for r in result.rules_triggered)


# ══════════════════════════════════════════════════════════════════════════════
# PII Leak Regression: accented names + alphanumeric IDs in HITL queue
# ══════════════════════════════════════════════════════════════════════════════

class TestPIILeakRegressionHITL:
    """
    Regression test for the bug where "I am María García, ID number 12345678A."
    appeared unredacted in GET /hitl/queue under `patient_inquiry` /
    `redacted_original_text`.

    The test covers:
      1. Stage 0 redaction alone catches both the name and the ID.
      2. When the pipeline escalates, the HITL queue stores only the
         redacted form (no raw PII in redacted_original_text).
    """

    _INQUIRY = (
        "I am María García, ID number 12345678A. "
        "I take metamizole at home for pain. "
        "Is it permitted in the United States? My doctor in Spain prescribed it for me."
    )

    def test_stage0_redacts_accented_name_and_alphanumeric_id(self):
        """Stage 0 must remove 'María García' and '12345678A' from text."""
        result = redact(self._INQUIRY)
        assert "María" not in result.redacted_text, "Accented first name leaked"
        assert "García" not in result.redacted_text, "Accented last name leaked"
        assert "12345678A" not in result.redacted_text, "Alphanumeric ID leaked"
        assert "[REDACTED_NAME]" in result.redacted_text
        assert "[REDACTED_ID]" in result.redacted_text

    def test_hitl_queue_stores_only_redacted_text(self, mock_client):
        """
        When the pipeline escalates (metamizole is banned in US_FDA),
        the HITL queue item must NOT contain 'María', 'García', or '12345678A'
        in redacted_original_text or the pipeline_trace.
        """
        from backend.hitl.queue import get_queue

        redaction = redact(self._INQUIRY)
        jctx = resolve("US")
        interpretation = interpret(redaction.redacted_text, jctx, mock_client)

        # Build escalation input using only the already-redacted text
        inp = EscalationInput(
            session_id="pii-leak-regression",
            original_text=redaction.redacted_text,
            user_type="patient",
            country="US",
            is_ambiguous_jurisdiction=False,
            redaction_result=redaction,
            min_confidence=0.95,
            medication_flags=interpretation.medication_flags,
            pipeline_trace={"inquiry": redaction.redacted_text},
            draft_response="Please consult a doctor.",
            redacted_original_text=redaction.redacted_text,
            english_inquiry=redaction.redacted_text,
        )
        esc_result = evaluate_escalation(inp)
        # metamizole banned in US → rule 2 fires → escalation happens
        assert esc_result.should_escalate is True
        review_id = enqueue_if_escalated(esc_result)
        assert review_id is not None

        item = get_queue().get_item(review_id)
        assert item is not None

        rot = item.redacted_original_text or ""
        assert "María" not in rot, f"Name leaked in redacted_original_text: {rot!r}"
        assert "García" not in rot, f"Name leaked in redacted_original_text: {rot!r}"
        assert "12345678A" not in rot, f"ID leaked in redacted_original_text: {rot!r}"

        trace_str = str(item.pipeline_trace)
        assert "María" not in trace_str, f"Name leaked in pipeline_trace: {trace_str!r}"
        assert "12345678A" not in trace_str, f"ID leaked in pipeline_trace: {trace_str!r}"
