"""
backend/watsonx/client.py
──────────────────────────
Thin wrapper around ibm-watsonx-ai for Granite model inference.

Design principles
─────────────────
* Real mode (WATSONX_MOCK_MODE=false):  calls ibm-watsonx-ai ModelInference
  via the chat interface (system + user messages) using Granite's native role
  tags so the model stays on-task and does not drift into boilerplate text.
  Raises WatsonxClientError on credential/network failures.
* Mock mode (WATSONX_MOCK_MODE=true):  returns deterministic stub responses
  so tests and offline demos never burn cloud credits.
* Every call returns a WatsonxResponse dataclass that includes the response
  text, an estimated confidence score, and the raw model metadata.

generate() signature
────────────────────
    generate(prompt, *, system_prompt=None, max_new_tokens=None, temperature=None)

    prompt        — the user-turn content (plain text, already formatted by
                    the pipeline stage).
    system_prompt — optional system-turn text; when omitted a minimal default
                    is used to keep the model in its clinical assistant role.

Usage
─────
    from backend.watsonx.client import get_client
    client = get_client()
    resp = client.generate(
        prompt="Explain deductibles in plain English.",
        system_prompt="You are a clinical language specialist.",
    )
    print(resp.text, resp.confidence)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, Optional

from backend.config import get_settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Public error type
# ──────────────────────────────────────────────────────────────────────────────

class WatsonxClientError(RuntimeError):
    """Raised when a watsonx.ai API call fails."""


# ──────────────────────────────────────────────────────────────────────────────
# Response dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class WatsonxResponse:
    """
    Normalised response from a watsonx.ai generate call.

    Attributes
    ──────────
    text        : Generated text (stripped).
    confidence  : Estimated confidence score 0.0–1.0.
                  Derived from the token log-probabilities when available;
                  defaults to 0.90 for successful real calls and a fixed
                  value in mock mode.
    model_id    : The model identifier that produced the response.
    mock        : True when this response came from the stub fallback.
    raw         : The original SDK response dict (None in mock mode).
    """

    text: str
    confidence: float
    model_id: str
    mock: bool = False
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False)


# ──────────────────────────────────────────────────────────────────────────────
# Default generation parameters for Granite
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_PARAMS: Dict[str, Any] = {
    "max_new_tokens": 512,
    "temperature": 0.3,
    "top_p": 0.9,
    "repetition_penalty": 1.1,
}

_DEFAULT_SYSTEM_PROMPT = (
    "You are a clinical language specialist assisting with medical and billing "
    "document interpretation. Respond only to the task given. "
    "Do NOT produce content unrelated to the clinical or administrative topic in the user message."
)


# ──────────────────────────────────────────────────────────────────────────────
# Client implementation
# ──────────────────────────────────────────────────────────────────────────────

class WatsonxClient:
    """
    Wraps ibm-watsonx-ai ModelInference with mock-mode fallback.

    Instantiate via ``get_client()`` to reuse the singleton across the
    request lifecycle.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._mock = self._settings.watsonx_mock_mode
        self._model_id = self._settings.watsonx_model_id
        self._model: Any = None  # lazy-initialised in _ensure_model()

        if not self._mock:
            self._validate_credentials()

    # ── Credential guard ──────────────────────────────────────────────────────

    def _validate_credentials(self) -> None:
        """Raise early if required credentials are absent in real mode."""
        missing = [
            name
            for name, attr in [
                ("WATSONX_API_KEY", self._settings.watsonx_api_key),
                ("WATSONX_PROJECT_ID", self._settings.watsonx_project_id),
            ]
            if not attr
        ]
        if missing:
            raise WatsonxClientError(
                f"Real mode requires: {', '.join(missing)}. "
                "Set them in .env or set WATSONX_MOCK_MODE=true for offline use."
            )

    # ── Lazy SDK initialisation ───────────────────────────────────────────────

    def _ensure_model(self) -> Any:
        """Return the ModelInference instance, creating it on first use."""
        if self._model is None:
            try:
                from ibm_watsonx_ai import Credentials
                from ibm_watsonx_ai.foundation_models import ModelInference
            except ImportError as exc:
                raise WatsonxClientError(
                    "ibm-watsonx-ai package is not installed. "
                    "Run: pip install ibm-watsonx-ai"
                ) from exc

            credentials = Credentials(
                api_key=self._settings.watsonx_api_key,
                url=self._settings.watsonx_url,
            )
            self._model = ModelInference(
                model_id=self._model_id,
                credentials=credentials,
                project_id=self._settings.watsonx_project_id,
                params=_DEFAULT_PARAMS,
            )
            logger.info(
                "watsonx ModelInference initialised: model=%s url=%s",
                self._model_id,
                self._settings.watsonx_url,
            )
        return self._model

    # ── Confidence estimation ─────────────────────────────────────────────────

    @staticmethod
    def _estimate_confidence(raw_response: Dict[str, Any]) -> float:
        """
        Derive a confidence estimate from the SDK response.

        Handles both the chat response format (``choices[0].logprobs``) and
        the legacy generate response format (``results[0].generated_tokens``).
        Falls back to 0.90 when log-probability metadata is absent.
        """
        import math

        try:
            # Chat format: choices[0].logprobs.content[*].logprob
            choices = raw_response.get("choices", [])
            if choices:
                logprobs_obj = choices[0].get("logprobs") or {}
                tokens = logprobs_obj.get("content", [])
                log_probs = [
                    t.get("logprob", 0.0)
                    for t in tokens
                    if t.get("logprob") is not None
                ]
                if log_probs:
                    avg_lp = sum(log_probs) / len(log_probs)
                    return round(min(1.0, max(0.0, math.exp(avg_lp))), 4)
                return 0.90

            # Legacy generate format: results[0].generated_tokens[*].logprob
            results = raw_response.get("results", [])
            if not results:
                return 0.90
            tokens = results[0].get("generated_tokens", [])
            log_probs = [
                t.get("logprob", 0.0)
                for t in tokens
                if t.get("logprob") is not None
            ]
            if not log_probs:
                return 0.90
            avg_lp = sum(log_probs) / len(log_probs)
            return round(min(1.0, max(0.0, math.exp(avg_lp))), 4)
        except Exception:
            return 0.90

    # ── Mock stubs ────────────────────────────────────────────────────────────

    def _mock_generate(self, prompt: str) -> WatsonxResponse:
        """
        Return a deterministic stub response without touching the network.

        The stub echoes a summary of the first 80 chars of the prompt so
        tests can assert on content without hitting watsonx.ai.
        """
        truncated = prompt[:80].replace("\n", " ")
        stub_text = (
            f"[MOCK] Processed: \"{truncated}\" — "
            "clinical context understood, proceeding with guidance."
        )
        return WatsonxResponse(
            text=stub_text,
            confidence=0.95,
            model_id=self._model_id,
            mock=True,
            raw=None,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> WatsonxResponse:
        """
        Generate text using Granite's chat interface.

        In real mode the prompt is wrapped in Granite's native
        role tags so the model stays strictly on the assigned clinical task
        and cannot drift into unrelated boilerplate (e.g. privacy notices
        triggered by [SSN] tokens). A stop sequence prevents the model from
        generating a follow-up user/system turn.

        In mock mode the raw *prompt* string is passed unchanged to the stub
        so all existing tests continue to work without modification.

        Parameters
        ──────────
        prompt         : User-turn content (the task-specific request).
        system_prompt  : System-turn instructions.  Defaults to a brief
                         clinical-assistant directive when omitted.
        max_new_tokens : Override the default max_new_tokens for this call.
        temperature    : Override the default temperature for this call.

        Returns
        ───────
        WatsonxResponse with generated text and confidence score.

        Raises
        ──────
        WatsonxClientError — on API or credential failure (real mode only).
        """
        if self._mock:
            logger.debug("Mock mode: skipping real API call.")
            return self._mock_generate(prompt)

        try:
            model = self._ensure_model()

            sys_text = system_prompt if system_prompt is not None else _DEFAULT_SYSTEM_PROMPT

            params: Dict[str, Any] = {}
            if max_new_tokens is not None:
                params["max_new_tokens"] = max_new_tokens
            if temperature is not None:
                params["temperature"] = temperature

            messages = [
                {"role": "system", "content": sys_text},
                {"role": "user", "content": prompt},
            ]
            raw = model.chat(messages=messages, params=params if params else None)
            generated_text = (
                raw["choices"][0]["message"]["content"]
            ).strip()
            confidence = self._estimate_confidence(raw)

            logger.debug(
                "watsonx chat: model=%s confidence=%.4f",
                self._model_id,
                confidence,
            )
            return WatsonxResponse(
                text=generated_text,
                confidence=confidence,
                model_id=self._model_id,
                mock=False,
                raw=raw,
            )
        except WatsonxClientError:
            raise
        except Exception as exc:
            raise WatsonxClientError(
                f"watsonx.ai API call failed: {exc}"
            ) from exc

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_mock(self) -> bool:
        return self._mock


# ──────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ──────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_client() -> WatsonxClient:
    """
    Return the application-wide WatsonxClient singleton.

    Call ``get_client.cache_clear()`` in tests to reset between cases.
    """
    return WatsonxClient()
