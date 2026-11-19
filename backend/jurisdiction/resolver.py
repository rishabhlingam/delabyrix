"""
backend/jurisdiction/resolver.py
─────────────────────────────────
Deterministic jurisdiction resolver.

Takes an ISO 3166-1 alpha-2 country code and returns a JurisdictionContext
dataclass that all downstream pipeline stages can consume without further
calls to rules.py.

Design note (from architecture.md §9):
  "The resolver is deterministic (no LLM call) — it uses a static lookup
  table in backend/jurisdiction/rules.py."

No I/O, no network calls, no LLM calls happen here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.jurisdiction.rules import get_rule, is_known_country, FALLBACK_RULE


@dataclass(frozen=True)
class JurisdictionContext:
    """
    Resolved regulatory and cultural context for a given country.

    Attributes
    ──────────
    country_code    ISO 3166-1 alpha-2 (upper-cased, as supplied)
    country_name    Human-readable country name
    registry        Which medication registry applies: US_FDA | EU_EMA | OTHER
    privacy_law     Applicable privacy framework: HIPAA | GDPR | UK_GDPR | OTHER | …
    cultural_norms  Coarse cultural-norm region tag for Stage-3 prompting
    region          WHO geographic region for BI bucketing
    is_ambiguous    True when country_code was not in the explicit lookup table
    """

    country_code: str
    country_name: str
    registry: str
    privacy_law: str
    cultural_norms: str
    region: str
    is_ambiguous: bool = field(default=False)

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def uses_fda(self) -> bool:
        """True if the FDA Orange Book is the applicable medication registry."""
        return self.registry == "US_FDA"

    @property
    def uses_ema(self) -> bool:
        """True if the EU EMA Union Register is the applicable registry."""
        return self.registry == "EU_EMA"

    @property
    def requires_hipaa(self) -> bool:
        return self.privacy_law == "HIPAA"

    @property
    def requires_gdpr(self) -> bool:
        return self.privacy_law in ("GDPR", "UK_GDPR")

    def to_dict(self) -> dict:
        return {
            "country_code": self.country_code,
            "country_name": self.country_name,
            "registry": self.registry,
            "privacy_law": self.privacy_law,
            "cultural_norms": self.cultural_norms,
            "region": self.region,
            "is_ambiguous": self.is_ambiguous,
        }


def resolve(country_code: str) -> JurisdictionContext:
    """
    Resolve the regulatory and cultural context for *country_code*.

    Parameters
    ──────────
    country_code : ISO 3166-1 alpha-2 string (case-insensitive).

    Returns
    ───────
    JurisdictionContext with ``is_ambiguous=True`` when the country code is not
    in the explicit rule table (HITL escalation should fire in this case).

    Never raises — always returns a usable context.
    """
    code = country_code.strip().upper() if country_code else ""
    ambiguous = not is_known_country(code)
    rule = get_rule(code)

    return JurisdictionContext(
        country_code=code,
        country_name=rule["country_name"],
        registry=rule["registry"],
        privacy_law=rule["privacy_law"],
        cultural_norms=rule["cultural_norms"],
        region=rule["region"],
        is_ambiguous=ambiguous,
    )


if __name__ == "__main__":
    for code in ["US", "DE", "IN", "ZZ"]:
        ctx = resolve(code)
        print(f"{code}: registry={ctx.registry}, privacy={ctx.privacy_law}, "
              f"ambiguous={ctx.is_ambiguous}")
