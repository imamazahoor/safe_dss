"""
SAFE — Healthcare Coding Standards
----------------------------------
Central registry of terminology codes used across the app.

Kept as a flat dict structure so it's trivial to extend and easy for
the backend layer to reuse when emitting FHIR Observation / Condition
resources.

References:
  - LOINC:     https://loinc.org
  - SNOMED CT: https://www.snomed.org
  - UCUM:      https://ucum.org
"""

# ============================================================
# LOINC codes for lab observations
# ============================================================
# Source: loinc.org search for the standard clinical lab panels.
# These codes correspond to serum/plasma measurements appropriate
# for ICU / sepsis workup.
LOINC = {
    "lactate":    {"code": "2524-7",  "display": "Lactate [Moles/volume] in Serum or Plasma"},
    "wbc":        {"code": "6690-2",  "display": "Leukocytes [#/volume] in Blood by Automated count"},
    "creatinine": {"code": "2160-0",  "display": "Creatinine [Mass/volume] in Serum or Plasma"},
    "platelets":  {"code": "777-3",   "display": "Platelets [#/volume] in Blood by Automated count"},
    "bun":        {"code": "3094-0",  "display": "Urea nitrogen [Mass/volume] in Serum or Plasma"},
    "glucose":    {"code": "2345-7",  "display": "Glucose [Mass/volume] in Serum or Plasma"},
}


# ============================================================
# UCUM units for each measurement
# ============================================================
# UCUM is the standard for units of measure. These strings are
# UCUM-compliant and can be emitted directly in FHIR Quantity.unit.
UCUM = {
    "lactate":    "mmol/L",
    "wbc":        "10*9/L",   # strict UCUM syntax for x10^9/L
    "creatinine": "mg/dL",
    "platelets":  "10*9/L",
    "bun":        "mg/dL",
    "glucose":    "mg/dL",
    "hr":         "/min",
    "map":        "mm[Hg]",   # UCUM bracket notation for mmHg
    "sbp":        "mm[Hg]",
    "temp":       "Cel",
    "resp":       "/min",
    "o2sat":      "%",
}


# ============================================================
# SNOMED CT codes for risk tiers
# ============================================================
# These concept IDs are real SNOMED CT risk-level codes. They let the
# backend emit FHIR Observation resources with a valueCodeableConcept
# pointing to a standard clinical vocabulary rather than free text.
SNOMED_RISK_TIER = {
    "Low":      {"code": "723506003", "display": "Risk level low"},
    "Moderate": {"code": "723507007", "display": "Risk level moderate"},
    "High":     {"code": "723508002", "display": "Risk level high"},
}


# Sepsis-related SNOMED concepts (for future backend emission)
SNOMED_SEPSIS = {
    "sepsis":          {"code": "91302008",  "display": "Sepsis (disorder)"},
    "septic_shock":    {"code": "76571007",  "display": "Septic shock (disorder)"},
    "sirs":            {"code": "238149007", "display": "Systemic inflammatory response syndrome"},
    "suspected_sepsis":{"code": "432254000", "display": "Suspected sepsis"},
}


# ============================================================
# Helper: format a code for display
# ============================================================
def loinc_ref(lab_key: str) -> str:
    """Return 'LOINC 2524-7' style reference string, or empty if not found."""
    entry = LOINC.get(lab_key)
    return f"LOINC {entry['code']}" if entry else ""


def snomed_tier_ref(tier: str) -> str:
    """Return 'SNOMED 723508002' style reference string."""
    entry = SNOMED_RISK_TIER.get(tier)
    return f"SNOMED CT {entry['code']}" if entry else ""


def ucum_unit(key: str) -> str:
    """Return the UCUM-compliant unit string for a measurement."""
    return UCUM.get(key, "")