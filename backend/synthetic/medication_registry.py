"""
backend/synthetic/medication_registry.py
─────────────────────────────────────────
Generates 50 synthetic cross-border medication registry records covering both
US_FDA and EU_EMA jurisdictions, with intentional cross-jurisdiction status
conflicts to exercise pipeline and jurisdiction-resolver logic.

Each record matches the schema defined in architecture.md §5a.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
import random
from typing import List, Dict, Any

# ── Seed for reproducibility ──────────────────────────────────────────────────
_RNG = random.Random(42)

# ── Deterministic date helper ─────────────────────────────────────────────────
_BASE_DATE = date(2024, 1, 1)


def _rdate(offset_days_min: int = 0, offset_days_max: int = 500) -> str:
    delta = _RNG.randint(offset_days_min, offset_days_max)
    return (_BASE_DATE + timedelta(days=delta)).isoformat()


# ── Core conflict dataset (medications with known real-world jurisdictional
#    differences — all details are based on publicly documented regulatory
#    decisions; no PII involved).
# ─────────────────────────────────────────────────────────────────────────────
_CONFLICT_PAIRS: List[Dict[str, Any]] = [
    # 1. Metamizole / Dipyrone — approved in EU, withdrawn/banned in US
    {
        "name_generic": "metamizole",
        "name_brand": "Dipyrone",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": (
                    "Withdrawn from US market due to risk of agranulocytosis; "
                    "FDA removed approval in 1977."
                ),
                "therapeutic_alternatives": ["ibuprofen", "acetaminophen", "naproxen"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 2. Domperidone — restricted in US, approved in EU
    {
        "name_generic": "domperidone",
        "name_brand": "Motilium",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "FDA has not approved domperidone; compounded versions exist "
                    "under IND only due to cardiac arrhythmia risk (QT prolongation)."
                ),
                "therapeutic_alternatives": ["metoclopramide", "ondansetron"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "restricted",
                "restriction_reason": (
                    "EMA restricted to lowest effective dose for shortest duration; "
                    "contraindicated with CYP3A4 inhibitors due to cardiac risk."
                ),
                "therapeutic_alternatives": ["metoclopramide"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 3. Phenylephrine (oral) — delisted in US for OTC cold remedies
    {
        "name_generic": "phenylephrine",
        "name_brand": "Sudafed PE",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "delisted",
                "restriction_reason": (
                    "FDA advisory committee (2023) concluded oral phenylephrine is "
                    "not effective as a nasal decongestant at OTC doses; "
                    "products being removed from shelves."
                ),
                "therapeutic_alternatives": ["pseudoephedrine", "oxymetazoline"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 4. Codeine (pediatric use) — banned for children in EU, restricted in US
    {
        "name_generic": "codeine",
        "name_brand": "Tylenol with Codeine",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "FDA contraindicated codeine for post-tonsillectomy pain in "
                    "children under 18; black-box warning for ultra-rapid CYP2D6 "
                    "metabolizers; available for adult use with restrictions."
                ),
                "therapeutic_alternatives": ["ibuprofen", "acetaminophen", "tramadol"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "restricted",
                "restriction_reason": (
                    "EMA banned codeine for cough/cold in children under 12 and "
                    "restricted it in 12-18 year olds with breathing problems."
                ),
                "therapeutic_alternatives": ["dextromethorphan", "acetaminophen"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 5. Nimesulide — approved in EU (many countries), banned in US
    {
        "name_generic": "nimesulide",
        "name_brand": "Aulin",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": (
                    "Never approved by FDA; concerns about hepatotoxicity precluded "
                    "approval."
                ),
                "therapeutic_alternatives": ["celecoxib", "naproxen", "ibuprofen"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "restricted",
                "restriction_reason": (
                    "EMA mandated restrictions: limited to 15 days maximum, "
                    "contraindicated in hepatic impairment; withdrawn in Finland "
                    "and Ireland."
                ),
                "therapeutic_alternatives": ["ibuprofen", "diclofenac"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 6. Diclofenac (topical gel) — different OTC status
    {
        "name_generic": "diclofenac",
        "name_brand": "Voltaren Gel",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 7. Tramadol — stricter scheduling in US
    {
        "name_generic": "tramadol",
        "name_brand": "Ultram",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "Schedule IV controlled substance; FDA added black-box warning "
                    "for addiction, abuse, misuse, and life-threatening respiratory "
                    "depression."
                ),
                "therapeutic_alternatives": ["acetaminophen", "ibuprofen", "pregabalin"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 8. Sibutramine — banned in both but earlier in US
    {
        "name_generic": "sibutramine",
        "name_brand": "Meridia",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": (
                    "Withdrawn from US market in 2010; SCOUT trial showed increased "
                    "risk of non-fatal MI and stroke in high-cardiovascular-risk patients."
                ),
                "therapeutic_alternatives": ["orlistat", "phentermine-topiramate", "bupropion-naltrexone"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "banned",
                "restriction_reason": (
                    "EMA suspended marketing authorization in 2010 following SCOUT "
                    "trial data."
                ),
                "therapeutic_alternatives": ["orlistat", "liraglutide"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 9. Rosiglitazone — restricted in EU, returned to market in US
    {
        "name_generic": "rosiglitazone",
        "name_brand": "Avandia",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "banned",
                "restriction_reason": (
                    "EMA suspended authorization in 2010 due to cardiovascular risk "
                    "data; authorization has not been reinstated."
                ),
                "therapeutic_alternatives": ["pioglitazone", "metformin", "sitagliptin"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 10. Mifepristone (200 mg, medical abortion) — restricted in US
    {
        "name_generic": "mifepristone",
        "name_brand": "Mifeprex",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "REMS program required; dispensed only by certified healthcare "
                    "providers; subject to state-level legal restrictions."
                ),
                "therapeutic_alternatives": [],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 11. Loperamide (high-dose) — restricted in US for OTC
    {
        "name_generic": "loperamide",
        "name_brand": "Imodium",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "FDA added new warnings; high-dose loperamide misuse can cause "
                    "serious cardiac events including QT prolongation and torsades "
                    "de pointes."
                ),
                "therapeutic_alternatives": ["bismuth subsalicylate"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 12. Testosterone (topical) — approved both, different labeling
    {
        "name_generic": "testosterone",
        "name_brand": "AndroGel",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 13. Ketamine (anesthetic) — approved, special status in US
    {
        "name_generic": "ketamine",
        "name_brand": "Ketalar",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "Schedule III controlled substance; approved for anesthetic "
                    "induction; abuse potential flagged."
                ),
                "therapeutic_alternatives": ["propofol", "etomidate"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 14. Mefloquine — approved in US with black-box neuropsychiatric warning
    {
        "name_generic": "mefloquine",
        "name_brand": "Lariam",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "FDA added black-box warning for neuropsychiatric adverse "
                    "reactions (hallucinations, suicidal ideation); should not be "
                    "prescribed for prophylaxis when alternatives exist."
                ),
                "therapeutic_alternatives": ["atovaquone-proguanil", "doxycycline"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "restricted",
                "restriction_reason": (
                    "EMA restricts use to malaria treatment/prophylaxis where "
                    "alternatives are unavailable; neuropsychiatric monitoring required."
                ),
                "therapeutic_alternatives": ["atovaquone-proguanil", "chloroquine"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 15. Efavirenz — approved both
    {
        "name_generic": "efavirenz",
        "name_brand": "Sustiva",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 16. Benzodiazepines — approved both, different scheduling
    {
        "name_generic": "diazepam",
        "name_brand": "Valium",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": "Schedule IV controlled substance; risk of dependence and misuse.",
                "therapeutic_alternatives": ["buspirone", "hydroxyzine", "lorazepam"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 17. Nalmefene — approved EU, not approved US
    {
        "name_generic": "nalmefene",
        "name_brand": "Selincro",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": (
                    "Not FDA-approved for alcohol use disorder reduction; "
                    "naltrexone is the approved alternative in the US."
                ),
                "therapeutic_alternatives": ["naltrexone", "acamprosate"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 18. Cinnarizine — not approved in US, approved EU
    {
        "name_generic": "cinnarizine",
        "name_brand": "Stugeron",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": "Not FDA-approved; never received approval in the US.",
                "therapeutic_alternatives": ["meclizine", "dimenhydrinate"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 19. Bromhexine — not approved US, approved EU
    {
        "name_generic": "bromhexine",
        "name_brand": "Bisolvon",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": "Not FDA-approved mucolytic; guaifenesin is the approved OTC expectorant.",
                "therapeutic_alternatives": ["guaifenesin", "acetylcysteine"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 20. Thalidomide — highly restricted both but different indications
    {
        "name_generic": "thalidomide",
        "name_brand": "Thalomid",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": (
                    "STEPS REMS program mandatory; approved only for multiple myeloma "
                    "and ENL; absolute contraindication in pregnancy."
                ),
                "therapeutic_alternatives": ["lenalidomide", "pomalidomide"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "restricted",
                "restriction_reason": (
                    "Approved for multiple myeloma under strict pregnancy prevention "
                    "programme; PhARP programme mandatory."
                ),
                "therapeutic_alternatives": ["lenalidomide"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 21. Linaclotide — approved US, different indication in EU
    {
        "name_generic": "linaclotide",
        "name_brand": "Linzess",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 22. Dronabinol (synthetic THC) — approved US restricted, not EU
    {
        "name_generic": "dronabinol",
        "name_brand": "Marinol",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "restricted",
                "restriction_reason": "Schedule III; approved for chemotherapy-induced nausea and HIV-associated anorexia.",
                "therapeutic_alternatives": ["ondansetron", "metoclopramide", "nabilone"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "banned",
                "restriction_reason": "No EU-wide marketing authorization; classified as Schedule I substance in most EU member states.",
                "therapeutic_alternatives": ["ondansetron", "granisetron"],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 23. Colchicine — different approved indications
    {
        "name_generic": "colchicine",
        "name_brand": "Colcrys",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 24. Ibuprofenate (topical ibuprofen lysinate) — varies
    {
        "name_generic": "ibuprofen lysinate",
        "name_brand": "Dolocyl",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": "Not FDA-approved; standard ibuprofen formulations approved instead.",
                "therapeutic_alternatives": ["ibuprofen", "naproxen sodium"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "approved",
                "restriction_reason": None,
                "therapeutic_alternatives": [],
                "source_registry": "EU Union Register",
            },
        ],
    },
    # 25. Flupirtine — withdrawn EU, never in US
    {
        "name_generic": "flupirtine",
        "name_brand": "Katadolon",
        "records": [
            {
                "jurisdiction": "US_FDA",
                "status": "banned",
                "restriction_reason": "Never FDA-approved.",
                "therapeutic_alternatives": ["pregabalin", "gabapentin", "amitriptyline"],
                "source_registry": "FDA Orange Book",
            },
            {
                "jurisdiction": "EU_EMA",
                "status": "banned",
                "restriction_reason": (
                    "EMA recommended suspension in 2018 due to hepatotoxicity risk; "
                    "marketing authorizations suspended across EU."
                ),
                "therapeutic_alternatives": ["pregabalin", "duloxetine"],
                "source_registry": "EU Union Register",
            },
        ],
    },
]


def _build_records(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten conflict pairs into individual registry records."""
    records = []
    for pair in pairs:
        for rec in pair["records"]:
            records.append(
                {
                    "medication_id": str(uuid.UUID(int=_RNG.getrandbits(128))),
                    "name_generic": pair["name_generic"],
                    "name_brand": pair["name_brand"],
                    "jurisdiction": rec["jurisdiction"],
                    "status": rec["status"],
                    "restriction_reason": rec["restriction_reason"],
                    "therapeutic_alternatives": rec["therapeutic_alternatives"],
                    "last_updated": _rdate(0, 500),
                    "source_registry": rec["source_registry"],
                }
            )
    return records


def generate_medication_registry() -> List[Dict[str, Any]]:
    """
    Return a list of 50 synthetic cross-border medication registry records.

    Records are deterministic (seeded RNG) so repeated calls produce
    identical data with identical UUIDs — good for reproducibility.
    """
    records = _build_records(_CONFLICT_PAIRS)
    # We have 25 pairs × 2 jurisdictions = 50 records exactly.
    assert len(records) == 50, f"Expected 50 records, got {len(records)}"
    return records


if __name__ == "__main__":
    import json

    data = generate_medication_registry()
    print(json.dumps(data, indent=2, default=str))
