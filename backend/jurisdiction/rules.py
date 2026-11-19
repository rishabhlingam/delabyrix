"""
backend/jurisdiction/rules.py
──────────────────────────────
Static lookup table: ISO 3166-1 alpha-2 country code  →  regulatory regime.

The resolver is intentionally deterministic — no LLM call, no I/O.
Data is loaded once at import time.

Regime structure
────────────────
  registry       — which medication registry applies (US_FDA | EU_EMA | OTHER)
  privacy_law    — applicable privacy framework (HIPAA | GDPR | OTHER)
  cultural_norms — coarse cultural-norm region tag (useful for Stage 3 prompting)
  region         — WHO geographic region (for BI bucketing)
"""

from __future__ import annotations

from typing import Dict, Any

# ── Type alias ────────────────────────────────────────────────────────────────
JurisdictionRule = Dict[str, str]

# ── Core lookup table ─────────────────────────────────────────────────────────
# Countries are grouped by regulatory regime; unlisted countries fall through
# to the FALLBACK_RULE.

JURISDICTION_RULES: Dict[str, JurisdictionRule] = {
    # ── United States ─────────────────────────────────────────────────────────
    "US": {
        "country_name": "United States",
        "registry": "US_FDA",
        "privacy_law": "HIPAA",
        "cultural_norms": "western_individualist",
        "region": "AMRO",
    },
    # ── Canada ────────────────────────────────────────────────────────────────
    "CA": {
        "country_name": "Canada",
        "registry": "US_FDA",          # Health Canada; use FDA as closest proxy
        "privacy_law": "PIPEDA",
        "cultural_norms": "western_individualist",
        "region": "AMRO",
    },
    # ── Mexico ────────────────────────────────────────────────────────────────
    "MX": {
        "country_name": "Mexico",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "latin_american",
        "region": "AMRO",
    },
    # ── Brazil ───────────────────────────────────────────────────────────────
    "BR": {
        "country_name": "Brazil",
        "registry": "OTHER",
        "privacy_law": "LGPD",
        "cultural_norms": "latin_american",
        "region": "AMRO",
    },
    # ── Colombia ─────────────────────────────────────────────────────────────
    "CO": {
        "country_name": "Colombia",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "latin_american",
        "region": "AMRO",
    },
    # ── Argentina ────────────────────────────────────────────────────────────
    "AR": {
        "country_name": "Argentina",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "latin_american",
        "region": "AMRO",
    },
    # ── Chile ────────────────────────────────────────────────────────────────
    "CL": {
        "country_name": "Chile",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "latin_american",
        "region": "AMRO",
    },
    # ── EU member states — EMA applies ───────────────────────────────────────
    "AT": {
        "country_name": "Austria",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "BE": {
        "country_name": "Belgium",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "BG": {
        "country_name": "Bulgaria",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "HR": {
        "country_name": "Croatia",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "CY": {
        "country_name": "Cyprus",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "southern_european",
        "region": "EURO",
    },
    "CZ": {
        "country_name": "Czech Republic",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "DK": {
        "country_name": "Denmark",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "nordic",
        "region": "EURO",
    },
    "EE": {
        "country_name": "Estonia",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "nordic",
        "region": "EURO",
    },
    "FI": {
        "country_name": "Finland",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "nordic",
        "region": "EURO",
    },
    "FR": {
        "country_name": "France",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "DE": {
        "country_name": "Germany",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "GR": {
        "country_name": "Greece",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "southern_european",
        "region": "EURO",
    },
    "HU": {
        "country_name": "Hungary",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "IE": {
        "country_name": "Ireland",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "IT": {
        "country_name": "Italy",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "southern_european",
        "region": "EURO",
    },
    "LV": {
        "country_name": "Latvia",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "nordic",
        "region": "EURO",
    },
    "LT": {
        "country_name": "Lithuania",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "LU": {
        "country_name": "Luxembourg",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "MT": {
        "country_name": "Malta",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "southern_european",
        "region": "EURO",
    },
    "NL": {
        "country_name": "Netherlands",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "PL": {
        "country_name": "Poland",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "PT": {
        "country_name": "Portugal",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "southern_european",
        "region": "EURO",
    },
    "RO": {
        "country_name": "Romania",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "SK": {
        "country_name": "Slovakia",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "SI": {
        "country_name": "Slovenia",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "eastern_european",
        "region": "EURO",
    },
    "ES": {
        "country_name": "Spain",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "southern_european",
        "region": "EURO",
    },
    "SE": {
        "country_name": "Sweden",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "nordic",
        "region": "EURO",
    },
    # ── Non-EU European countries ─────────────────────────────────────────────
    "GB": {
        "country_name": "United Kingdom",
        "registry": "EU_EMA",          # MHRA; use EMA as proxy post-Brexit
        "privacy_law": "UK_GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "NO": {
        "country_name": "Norway",
        "registry": "EU_EMA",          # EEA member; EMA applies
        "privacy_law": "GDPR",
        "cultural_norms": "nordic",
        "region": "EURO",
    },
    "IS": {
        "country_name": "Iceland",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "nordic",
        "region": "EURO",
    },
    "LI": {
        "country_name": "Liechtenstein",
        "registry": "EU_EMA",
        "privacy_law": "GDPR",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    "CH": {
        "country_name": "Switzerland",
        "registry": "EU_EMA",          # Swissmedic; EMA as proxy
        "privacy_law": "OTHER",
        "cultural_norms": "western_individualist",
        "region": "EURO",
    },
    # ── South Asia ────────────────────────────────────────────────────────────
    "IN": {
        "country_name": "India",
        "registry": "OTHER",
        "privacy_law": "DPDPA",
        "cultural_norms": "south_asian",
        "region": "SEARO",
    },
    "PK": {
        "country_name": "Pakistan",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "south_asian",
        "region": "EMRO",
    },
    "BD": {
        "country_name": "Bangladesh",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "south_asian",
        "region": "SEARO",
    },
    "LK": {
        "country_name": "Sri Lanka",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "south_asian",
        "region": "SEARO",
    },
    # ── East / Southeast Asia ─────────────────────────────────────────────────
    "CN": {
        "country_name": "China",
        "registry": "OTHER",
        "privacy_law": "PIPL",
        "cultural_norms": "east_asian_collectivist",
        "region": "WPRO",
    },
    "JP": {
        "country_name": "Japan",
        "registry": "OTHER",
        "privacy_law": "APPI",
        "cultural_norms": "east_asian_collectivist",
        "region": "WPRO",
    },
    "KR": {
        "country_name": "South Korea",
        "registry": "OTHER",
        "privacy_law": "PIPA",
        "cultural_norms": "east_asian_collectivist",
        "region": "WPRO",
    },
    "PH": {
        "country_name": "Philippines",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "southeast_asian",
        "region": "WPRO",
    },
    "AU": {
        "country_name": "Australia",
        "registry": "OTHER",
        "privacy_law": "PRIVACY_ACT_AU",
        "cultural_norms": "western_individualist",
        "region": "WPRO",
    },
    "NZ": {
        "country_name": "New Zealand",
        "registry": "OTHER",
        "privacy_law": "PRIVACY_ACT_NZ",
        "cultural_norms": "western_individualist",
        "region": "WPRO",
    },
    # ── Middle East / North Africa ────────────────────────────────────────────
    "SA": {
        "country_name": "Saudi Arabia",
        "registry": "OTHER",
        "privacy_law": "PDPL_SA",
        "cultural_norms": "middle_eastern",
        "region": "EMRO",
    },
    "AE": {
        "country_name": "United Arab Emirates",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "middle_eastern",
        "region": "EMRO",
    },
    "EG": {
        "country_name": "Egypt",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "middle_eastern",
        "region": "EMRO",
    },
    "TR": {
        "country_name": "Turkey",
        "registry": "OTHER",
        "privacy_law": "KVKK",
        "cultural_norms": "middle_eastern",
        "region": "EURO",   # WHO classifies Turkey in EURO
    },
    # ── Sub-Saharan Africa ────────────────────────────────────────────────────
    "NG": {
        "country_name": "Nigeria",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "sub_saharan_african",
        "region": "AFRO",
    },
    "ZA": {
        "country_name": "South Africa",
        "registry": "OTHER",
        "privacy_law": "POPIA",
        "cultural_norms": "sub_saharan_african",
        "region": "AFRO",
    },
    "KE": {
        "country_name": "Kenya",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "sub_saharan_african",
        "region": "AFRO",
    },
    "GH": {
        "country_name": "Ghana",
        "registry": "OTHER",
        "privacy_law": "OTHER",
        "cultural_norms": "sub_saharan_african",
        "region": "AFRO",
    },
}

# ── Fallback for countries not explicitly listed ───────────────────────────────
FALLBACK_RULE: JurisdictionRule = {
    "country_name": "Unknown",
    "registry": "OTHER",
    "privacy_law": "OTHER",
    "cultural_norms": "general",
    "region": "UNKNOWN",
}


def get_rule(country_code: str) -> JurisdictionRule:
    """
    Return the jurisdiction rule for a given ISO 3166-1 alpha-2 country code.

    Always returns a valid rule (falls back to FALLBACK_RULE for unknown codes).
    """
    return JURISDICTION_RULES.get(country_code.upper(), FALLBACK_RULE)


def is_known_country(country_code: str) -> bool:
    """Return True if the country code has an explicit rule entry."""
    return country_code.upper() in JURISDICTION_RULES
