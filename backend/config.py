"""
backend/config.py
──────────────────
Application settings loaded from environment variables (and .env) via
pydantic-settings.

All secrets live in .env (excluded from source control via .bobignore).
No default values are provided for credentials — they must be set before
real watsonx.ai calls are attempted (the client will raise a clear error
when WATSONX_MOCK_MODE=false and credentials are missing).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All configurable values for the clinical AI agent backend.

    Fields with defaults can be used immediately without a .env file.
    Fields without defaults must be provided in .env or the environment
    when WATSONX_MOCK_MODE is false.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── watsonx.ai credentials ────────────────────────────────────────────────
    watsonx_api_key: Optional[str] = Field(default=None)
    watsonx_project_id: Optional[str] = Field(default=None)
    watsonx_url: str = Field(default="https://us-south.ml.cloud.ibm.com")
    watsonx_model_id: str = Field(default="ibm/granite-4-h-small")

    # ── Offline / test mode ───────────────────────────────────────────────────
    # Set WATSONX_MOCK_MODE=true to skip real API calls; deterministic stubs
    # are returned instead.  Useful for CI and offline demos.
    watsonx_mock_mode: bool = Field(default=False)

    # ── API security ──────────────────────────────────────────────────────────
    api_key: Optional[str] = Field(default=None)

    # ── Application settings ──────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    hitl_confidence_threshold: float = Field(default=0.70)

    # ── Synthetic data ────────────────────────────────────────────────────────
    synthetic_data_dir: str = Field(default="synthetic_data")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings singleton.

    Call ``get_settings.cache_clear()`` in tests to reload from a fresh
    environment.
    """
    return Settings()
