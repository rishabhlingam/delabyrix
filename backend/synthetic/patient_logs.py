"""
backend/synthetic/patient_logs.py
──────────────────────────────────
Generates 200 synthetic, zero-PII anonymized patient log records.

Each record matches the schema defined in architecture.md §5c:
  patient_id          — synthetic hash (not a real patient ID)
  age_band            — 18-30 | 31-45 | 46-60 | 61+
  nationality         — ISO 3166-1 alpha-2 country code
  condition_codes     — list of ICD-10 category codes only
  medications_current — list of INN drug names
  diet_flags          — e.g. halal, vegan, gluten-free
  interaction_language — BCP-47 language tag
  visit_type          — ER | ICU | outpatient | telehealth

No names, dates of birth, addresses, or any other PII are stored.
"""

from __future__ import annotations

import hashlib
import random
from typing import List, Dict, Any

# ── Seeded RNG for reproducibility ────────────────────────────────────────────
_RNG = random.Random(2024)

# ── Reference data pools ──────────────────────────────────────────────────────

_AGE_BANDS = ["18-30", "31-45", "46-60", "61+"]
_AGE_BAND_WEIGHTS = [0.20, 0.25, 0.30, 0.25]

_NATIONALITIES = [
    # North America
    "US", "CA", "MX",
    # Europe
    "GB", "DE", "FR", "ES", "IT", "NL", "PL", "PT", "SE",
    # South Asia
    "IN", "PK", "BD", "LK",
    # East Asia
    "CN", "JP", "KR", "PH",
    # Middle East
    "SA", "AE", "EG", "TR",
    # Latin America
    "BR", "CO", "AR", "CL",
    # Africa
    "NG", "ZA", "KE", "GH",
    # Oceania
    "AU", "NZ",
]
_NATIONALITY_WEIGHTS = [
    # North America
    0.20, 0.06, 0.04,
    # Europe
    0.07, 0.05, 0.04, 0.03, 0.02, 0.02, 0.01, 0.01, 0.01,
    # South Asia
    0.09, 0.03, 0.02, 0.01,
    # East Asia
    0.05, 0.03, 0.02, 0.02,
    # Middle East
    0.02, 0.02, 0.01, 0.01,
    # Latin America
    0.02, 0.01, 0.01, 0.01,
    # Africa
    0.01, 0.01, 0.01, 0.01,
    # Oceania
    0.02, 0.01,
]

# ICD-10 category codes (chapter-level, no patient-identifiable detail)
_ICD10_CATEGORIES = [
    "A00-B99",   # Infectious and parasitic diseases
    "C00-D49",   # Neoplasms
    "D50-D89",   # Blood diseases
    "E00-E89",   # Endocrine/metabolic (diabetes, thyroid)
    "F01-F99",   # Mental and behavioural disorders
    "G00-G99",   # Nervous system diseases
    "H00-H59",   # Eye diseases
    "H60-H95",   # Ear diseases
    "I00-I99",   # Circulatory system diseases
    "J00-J99",   # Respiratory system diseases
    "K00-K95",   # Digestive system diseases
    "L00-L99",   # Skin diseases
    "M00-M99",   # Musculoskeletal diseases
    "N00-N99",   # Genitourinary diseases
    "O00-O9A",   # Pregnancy/childbirth
    "P00-P96",   # Perinatal conditions
    "Q00-Q99",   # Congenital malformations
    "R00-R99",   # Symptoms/signs NEC
    "S00-T88",   # Injury/poisoning
    "Z00-Z99",   # Factors influencing health status
]

# INN medication names (commonly encountered in cross-border clinical settings)
_MEDICATIONS = [
    "metformin", "lisinopril", "amlodipine", "atorvastatin", "omeprazole",
    "levothyroxine", "metoprolol", "losartan", "albuterol", "gabapentin",
    "sertraline", "amoxicillin", "hydrochlorothiazide", "furosemide",
    "acetaminophen", "ibuprofen", "aspirin", "warfarin", "insulin glargine",
    "clopidogrel", "pantoprazole", "rosuvastatin", "duloxetine", "escitalopram",
    "tramadol", "diazepam", "codeine", "ondansetron", "prednisone",
    "dexamethasone", "azithromycin", "ciprofloxacin", "ceftriaxone",
    "heparin", "enoxaparin", "metronidazole", "fluconazole", "acyclovir",
    "tamsulosin", "finasteride", "sildenafil", "tadalafil", "clonazepam",
    "quetiapine", "olanzapine", "risperidone", "aripiprazole", "lithium",
    "valproate", "levetiracetam", "carbamazepine", "phenytoin",
    "colchicine", "allopurinol", "methotrexate", "hydroxychloroquine",
    "adalimumab", "etanercept", "infliximab", "tocilizumab",
    "budesonide", "fluticasone", "tiotropium", "montelukast",
    "simvastatin", "ezetimibe", "spironolactone", "bisoprolol",
    "ramipril", "valsartan", "digoxin", "amiodarone", "apixaban",
    "rivaroxaban", "dabigatran", "sitagliptin", "empagliflozin",
    "liraglutide", "insulin aspart", "glibenclamide",
    "domperidone", "metamizole", "nimesulide", "diclofenac",
]

_DIET_FLAGS = [
    "halal", "kosher", "vegan", "vegetarian", "gluten-free",
    "lactose-free", "low-sodium", "diabetic", "renal", "nut-free",
]

_LANGUAGES = [
    # BCP-47 tags and approximate weights matching nationality pool
    ("en", 0.30), ("es", 0.12), ("hi", 0.10), ("zh", 0.06),
    ("ar", 0.05), ("pt", 0.04), ("fr", 0.04), ("de", 0.03),
    ("ja", 0.03), ("ko", 0.03), ("ur", 0.03), ("bn", 0.03),
    ("tr", 0.02), ("sw", 0.02), ("ta", 0.02), ("nl", 0.02),
    ("pl", 0.01), ("it", 0.01), ("sv", 0.01), ("tl", 0.01),
]
_LANG_TAGS = [l[0] for l in _LANGUAGES]
_LANG_WEIGHTS = [l[1] for l in _LANGUAGES]

_VISIT_TYPES = ["ER", "ICU", "outpatient", "telehealth"]
_VISIT_WEIGHTS = [0.15, 0.08, 0.60, 0.17]


def _synthetic_patient_id(index: int) -> str:
    """Generate a deterministic, opaque synthetic hash — not a real ID."""
    raw = f"SYNTH-PATIENT-{index:05d}-DELABYRIX"
    return "P-" + hashlib.sha1(raw.encode()).hexdigest()[:12].upper()


def _weighted_choice(population: list, weights: list, rng: random.Random) -> Any:
    """Single weighted random choice using the provided RNG."""
    return rng.choices(population, weights=weights, k=1)[0]


def _make_record(index: int) -> Dict[str, Any]:
    """Generate a single patient log record."""
    n_conditions = _RNG.randint(1, 3)
    condition_codes = _RNG.sample(_ICD10_CATEGORIES, n_conditions)

    n_meds = _RNG.randint(0, 5)
    medications = _RNG.sample(_MEDICATIONS, n_meds)

    n_diet = _RNG.randint(0, 3)
    diet_flags = _RNG.sample(_DIET_FLAGS, n_diet)

    return {
        "patient_id": _synthetic_patient_id(index),
        "age_band": _weighted_choice(_AGE_BANDS, _AGE_BAND_WEIGHTS, _RNG),
        "nationality": _weighted_choice(_NATIONALITIES, _NATIONALITY_WEIGHTS, _RNG),
        "condition_codes": condition_codes,
        "medications_current": medications,
        "diet_flags": diet_flags,
        "interaction_language": _weighted_choice(_LANG_TAGS, _LANG_WEIGHTS, _RNG),
        "visit_type": _weighted_choice(_VISIT_TYPES, _VISIT_WEIGHTS, _RNG),
    }


def generate_patient_logs(count: int = 200) -> List[Dict[str, Any]]:
    """
    Return a list of ``count`` synthetic patient log records.

    Records are deterministic (seeded RNG) so repeated calls with the same
    ``count`` produce identical data — suitable for reproducible tests.
    No PII is present in any record.
    """
    return [_make_record(i) for i in range(count)]


if __name__ == "__main__":
    import json

    logs = generate_patient_logs()
    print(f"Generated {len(logs)} patient log records.")
    print(json.dumps(logs[:3], indent=2))
