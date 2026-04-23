"""
SAFE Data Service
-----------------
Single seam between the UI and the data layer.
Mock implementations now; real PostgreSQL queries later.
Function signatures stay stable so UI code never has to change.
"""

from typing import Optional
import pandas as pd
from datetime import datetime
import streamlit as st


# ============================================================
# AUTH
# ============================================================
_DEMO_USERS = {
    "admin": {
        "user_id": 1, "username": "admin", "password": "demo",
        "name": "Eugene Ho", "role": "admin",
    },
    "clinician": {
        "user_id": 2, "username": "clinician", "password": "demo",
        "name": "Dr. Imama Zahoor", "role": "clinician",
    },
}


def authenticate_user(username: str, password: str, selected_role: str) -> Optional[dict]:
    """Verify credentials AND role-tab match."""
    user = _DEMO_USERS.get(username.strip().lower())
    if user is None or user["password"] != password or user["role"] != selected_role:
        return None
    return {k: v for k, v in user.items() if k != "password"}


def log_login_attempt(username: str, success: bool, role: str) -> None:
    """TODO: INSERT into audit_log table once backend is ready."""
    status = "SUCCESS" if success else "FAILURE"
    print(f"[AUDIT] {datetime.utcnow().isoformat()} | LOGIN {status} | "
          f"user={username} | role={role}")


# ============================================================
# MOCK PATIENT STORE — lives in session_state so edits persist
# within a single session.
# ============================================================
# When PostgreSQL is wired in, the internals of every get_/update_/record_
# function below change. UI code stays identical.
def _seed_patients() -> list[dict]:
    """Initial 5 patients across 3 risk tiers."""
    return [
        # --- High risk (2) ---
        {
            "patient_id": "P001", "name": "Patient 001", "age": 67, "gender": "M",
            "unit": "MICU", "icu_hour": 48, "risk_tier": "High", "risk_score": 0.87,
            "admitted_at": "2026-04-18 09:12",
            "vitals": {"hr": 118, "map": 62, "sbp": 94, "temp": 38.6, "resp": 26, "o2sat": 93},
            "labs":   {"lactate": 3.4, "wbc": 15.2, "creatinine": 1.8, "platelets": 140, "bun": 32, "glucose": 168},
        },
        {
            "patient_id": "P002", "name": "Patient 002", "age": 71, "gender": "F",
            "unit": "SICU", "icu_hour": 36, "risk_tier": "High", "risk_score": 0.79,
            "admitted_at": "2026-04-18 21:45",
            "vitals": {"hr": 112, "map": 64, "sbp": 98, "temp": 38.2, "resp": 24, "o2sat": 94},
            "labs":   {"lactate": 2.8, "wbc": 13.8, "creatinine": 1.5, "platelets": 165, "bun": 28, "glucose": 152},
        },
        # --- Moderate risk (2) ---
        {
            "patient_id": "P003", "name": "Patient 003", "age": 54, "gender": "F",
            "unit": "SICU", "icu_hour": 22, "risk_tier": "Moderate", "risk_score": 0.52,
            "admitted_at": "2026-04-19 11:20",
            "vitals": {"hr": 96, "map": 72, "sbp": 110, "temp": 37.8, "resp": 20, "o2sat": 96},
            "labs":   {"lactate": 2.1, "wbc": 11.4, "creatinine": 1.2, "platelets": 195, "bun": 22, "glucose": 132},
        },
        {
            "patient_id": "P004", "name": "Patient 004", "age": 62, "gender": "M",
            "unit": "MICU", "icu_hour": 14, "risk_tier": "Moderate", "risk_score": 0.44,
            "admitted_at": "2026-04-19 19:08",
            "vitals": {"hr": 88, "map": 75, "sbp": 116, "temp": 37.4, "resp": 18, "o2sat": 97},
            "labs":   {"lactate": 1.8, "wbc": 10.2, "creatinine": 1.0, "platelets": 210, "bun": 19, "glucose": 118},
        },
        # --- Low risk (1) ---
        {
            "patient_id": "P005", "name": "Patient 005", "age": 45, "gender": "M",
            "unit": "MICU", "icu_hour": 9, "risk_tier": "Low", "risk_score": 0.14,
            "admitted_at": "2026-04-20 00:33",
            "vitals": {"hr": 78, "map": 86, "sbp": 122, "temp": 36.9, "resp": 16, "o2sat": 98},
            "labs":   {"lactate": 1.1, "wbc": 8.2, "creatinine": 0.9, "platelets": 245, "bun": 14, "glucose": 102},
        },
    ]


def _get_store() -> list[dict]:
    """Lazy-init the session-scoped patient store."""
    if "patients_store" not in st.session_state:
        st.session_state["patients_store"] = _seed_patients()
    return st.session_state["patients_store"]


# ============================================================
# DASHBOARD STATS
# ============================================================
def get_dashboard_stats() -> dict:
    """Top-of-dashboard summary: total patients, high alerts, avg risk."""
    # TODO: swap for aggregate SQL query
    patients = _get_store()
    total = len(patients)
    high = sum(1 for p in patients if p["risk_tier"] == "High")
    avg_risk = sum(p["risk_score"] for p in patients) / total if total else 0.0
    return {
        "total_patients": total,
        "high_risk_alerts": high,
        "avg_risk_score": round(avg_risk, 2),
    }


# ============================================================
# PATIENT QUERIES
# ============================================================
def get_active_patients() -> pd.DataFrame:
    """All currently-admitted ICU patients."""
    # TODO: SELECT ... FROM patient JOIN icu_stay JOIN risk_assessment ...
    return pd.DataFrame(_get_store())


def get_patients_by_tier(tier: str) -> list[dict]:
    """Filter active patients by risk tier ('High' | 'Moderate' | 'Low')."""
    return [p for p in _get_store() if p["risk_tier"] == tier]


def get_patient_detail(patient_id: str) -> Optional[dict]:
    """Full record for one patient, or None if not found."""
    for p in _get_store():
        if p["patient_id"] == patient_id:
            return p
    return None


# ============================================================
# PATIENT MUTATIONS
# ============================================================
def update_patient_profile(patient_id: str, updates: dict) -> bool:
    """Update demographics (name, age, gender, unit).

    TODO: UPDATE patient SET ... WHERE patient_id = %s
    """
    for p in _get_store():
        if p["patient_id"] == patient_id:
            for key in ("name", "age", "gender", "unit"):
                if key in updates:
                    p[key] = updates[key]
            print(f"[MOCK] Updated profile for {patient_id}: {updates}")
            return True
    return False


def record_new_measurement(patient_id: str, vitals: dict, labs: dict) -> bool:
    """Record a new hourly measurement (writes into Hourly_Measurement).

    For the mock, we overwrite the 'current' vitals/labs on the patient.
    TODO: INSERT INTO hourly_measurement (...) VALUES (...)
          Then trigger Risk_Assessment recomputation.
    """
    for p in _get_store():
        if p["patient_id"] == patient_id:
            p["vitals"].update({k: v for k, v in vitals.items() if v is not None})
            p["labs"].update({k: v for k, v in labs.items() if v is not None})
            print(f"[MOCK] Recorded measurement for {patient_id}")
            return True
    return False


def discharge_patient(patient_id: str) -> bool:
    """Remove patient from active queue.

    TODO: UPDATE icu_stay SET t_discharge = NOW() WHERE icu_stay_id = ...
    """
    store = _get_store()
    for i, p in enumerate(store):
        if p["patient_id"] == patient_id:
            removed = store.pop(i)
            print(f"[MOCK] Discharged {patient_id}: {removed['name']}")
            return True
    return False


# ============================================================
# ALERTS (stub for future screens)
# ============================================================
def get_pending_alerts() -> pd.DataFrame:
    return pd.DataFrame([
        {"alert_id": 101, "patient_id": "P001", "alert_level": "High",
         "risk_score": 0.87, "triggered_at": "2026-04-20 08:15", "status": "Pending"},
    ])


def record_alert_response(alert_id: int, user_id: int, action: str, notes: str = "") -> bool:
    print(f"[MOCK] Alert {alert_id} | User {user_id} | Action: {action} | Notes: {notes}")
    return True


# ============================================================
# RISK EXPLANATION — feature contributions to the risk score
# ============================================================
# Normal clinical reference ranges for each variable (source: HW7 thresholds).
# We use these to decide which direction a value is "abnormal" in and assign
# a mock contribution that roughly tracks deviation from the range.
_REFERENCE_RANGES = {
    "hr":         (60, 100,  "bpm"),
    "map":        (65, 100,  "mmHg"),
    "sbp":        (90, 140,  "mmHg"),
    "temp":       (36.0, 38.0, "°C"),
    "resp":       (12, 22,   "/min"),
    "o2sat":      (95, 100,  "%"),
    "lactate":    (0.5, 2.0, "mmol/L"),
    "wbc":        (4.0, 12.0, "x10⁹/L"),
    "creatinine": (0.6, 1.3, "mg/dL"),
    "platelets":  (150, 400, "x10⁹/L"),
    "bun":        (7, 20,    "mg/dL"),
    "glucose":    (70, 140,  "mg/dL"),
}

# Human-readable names
_PRETTY_NAMES = {
    "hr": "Heart rate", "map": "MAP", "sbp": "SBP", "temp": "Temperature",
    "resp": "Respiratory rate", "o2sat": "O₂ saturation",
    "lactate": "Lactate", "wbc": "WBC", "creatinine": "Creatinine",
    "platelets": "Platelets", "bun": "BUN", "glucose": "Glucose",
}


def _compute_contribution(name: str, value: float) -> Optional[dict]:
    """Classify a value against its reference range and mock a contribution score.

    Returns dict with direction, status, and weight — or None if within range.
    """
    if name not in _REFERENCE_RANGES:
        return None
    lo, hi, unit = _REFERENCE_RANGES[name]
    if value is None:
        return None

    if value > hi:
        # Above upper bound
        deviation = (value - hi) / max(hi - lo, 1)
        return {
            "name": _PRETTY_NAMES.get(name, name),
            "value": value,
            "unit": unit,
            "direction": "up",
            "status": "above normal",
            "contribution": round(min(0.35, 0.05 + 0.15 * deviation), 2),
        }
    if value < lo:
        deviation = (lo - value) / max(hi - lo, 1)
        return {
            "name": _PRETTY_NAMES.get(name, name),
            "value": value,
            "unit": unit,
            "direction": "down",
            "status": "below normal",
            "contribution": round(min(0.35, 0.05 + 0.15 * deviation), 2),
        }
    return None  # within normal range — doesn't contribute


def get_risk_explanation(patient_id: str, top_n: int = 5) -> list[dict]:
    """Return the top N contributing features for a patient's current risk score.

    TODO: swap for real feature-importance output from the deployed model.
    """
    patient = get_patient_detail(patient_id)
    if patient is None:
        return []

    contributions = []
    for name, val in patient["vitals"].items():
        c = _compute_contribution(name, val)
        if c:
            contributions.append(c)
    for name, val in patient["labs"].items():
        c = _compute_contribution(name, val)
        if c:
            contributions.append(c)

    # Sort by contribution descending, take top N
    contributions.sort(key=lambda x: x["contribution"], reverse=True)
    return contributions[:top_n]


# ============================================================
# RISK HISTORY — hourly risk score over time for the trend chart
# ============================================================
def get_risk_history(patient_id: str, hours: int = 24) -> pd.DataFrame:
    """Return the last N hours of risk scores for the trend chart.

    Mock: generates a plausible trajectory based on current score + tier.
    TODO: SELECT risk_score, t_prediction FROM risk_assessment
          WHERE patient_id = %s AND t_prediction > NOW() - INTERVAL '24 hours'
          ORDER BY t_prediction;
    """
    import numpy as np

    patient = get_patient_detail(patient_id)
    if patient is None:
        return pd.DataFrame(columns=["hour", "risk_score"])

    final = patient["risk_score"]
    tier = patient["risk_tier"]

    # Start lower; trend upward into current score for High, flatter for others
    rng = np.random.default_rng(seed=hash(patient_id) % 2**32)
    if tier == "High":
        start = max(0.15, final - 0.55)
    elif tier == "Moderate":
        start = max(0.10, final - 0.25)
    else:
        start = max(0.05, final - 0.08)

    # Linear-ish interpolation + jitter
    trajectory = np.linspace(start, final, hours)
    jitter = rng.normal(0, 0.03, size=hours)
    trajectory = np.clip(trajectory + jitter, 0.0, 1.0)
    trajectory[-1] = final  # ensure the endpoint matches the current score

    return pd.DataFrame({
        "hour": list(range(-hours + 1, 1)),  # -23, -22, ..., 0 (now)
        "risk_score": trajectory.round(3),
    })


# ============================================================
# RECOMMENDATIONS — hardcoded by tier (matches typical sepsis bundle)
# ============================================================
_RECOMMENDATIONS_BY_TIER = {
    "High": [
        "Initiate Hour-1 sepsis bundle immediately.",
        "Obtain blood cultures before antibiotics if feasible.",
        "Administer broad-spectrum IV antibiotics within 1 hour.",
        "Begin 30 mL/kg crystalloid for hypotension or lactate ≥ 4 mmol/L.",
        "Consider vasopressors for MAP < 65 mmHg after fluid resuscitation.",
        "Draw repeat lactate within 2 hours.",
    ],
    "Moderate": [
        "Reassess vitals and mental status every hour.",
        "Obtain lactate, WBC, and CBC if not drawn in past 4 hours.",
        "Start IV access and prepare for rapid fluid bolus if deterioration.",
        "Consider empiric antibiotics if infection source is identified.",
    ],
    "Low": [
        "Continue routine vital sign monitoring per ICU protocol.",
        "Document baseline labs and trend over next 4–6 hours.",
        "Reassess risk if new symptoms emerge or labs shift.",
    ],
}


def get_recommendations(risk_tier: str) -> list[str]:
    """Return preliminary recommendations for the given tier.

    TODO: swap for dynamic rule engine or LLM-generated recommendations
          based on the specific feature contributions and patient history.
    """
    return list(_RECOMMENDATIONS_BY_TIER.get(risk_tier, []))


# ============================================================
# CLASSIFICATION ACTIONS — confirm or reclassify
# ============================================================
def confirm_risk_classification(patient_id: str, user_id: int) -> bool:
    """Log that a clinician confirmed the model's classification.

    TODO: INSERT INTO classification_confirmations ...
    """
    print(f"[MOCK] User {user_id} CONFIRMED risk tier for {patient_id}")
    return True


def reclassify_patient(patient_id: str, new_tier: str, user_id: int,
                       reason: str = "") -> bool:
    """Allow the clinician to override the model's risk tier.

    TODO: INSERT INTO classification_overrides ... + UPDATE risk_assessment
    """
    for p in _get_store():
        if p["patient_id"] == patient_id:
            old_tier = p["risk_tier"]
            p["risk_tier"] = new_tier
            print(f"[MOCK] User {user_id} RECLASSIFIED {patient_id}: "
                  f"{old_tier} → {new_tier}. Reason: {reason}")
            return True
    return False

# ============================================================
# NEW PATIENT ADMISSION
# ============================================================
# Criteria thresholds from HW7 SAFE proxy definition.
# Each criterion triggered counts toward risk tier assignment.
def _count_safe_criteria(vitals: dict, labs: dict) -> tuple[int, list[str]]:
    """Count how many SAFE proxy criteria the snapshot triggers.

    Returns (count, list_of_triggered_names). Only counts criteria
    where the relevant value is provided — missing values do not count
    for or against the patient (matches real-world partial-data scenarios).
    """
    triggered = []

    # Lactate > 2 mmol/L
    if labs.get("lactate") is not None and labs["lactate"] > 2.0:
        triggered.append("Lactate > 2.0 mmol/L")
    # MAP < 65 mmHg
    if vitals.get("map") is not None and vitals["map"] < 65:
        triggered.append("MAP < 65 mmHg")
    # HR > 100 bpm
    if vitals.get("hr") is not None and vitals["hr"] > 100:
        triggered.append("HR > 100 bpm")
    # Resp > 22 /min
    if vitals.get("resp") is not None and vitals["resp"] > 22:
        triggered.append("Resp > 22 /min")
    # WBC < 4 or > 12
    wbc = labs.get("wbc")
    if wbc is not None and (wbc < 4.0 or wbc > 12.0):
        triggered.append("WBC abnormal")
    # Temp < 36 or > 38
    temp = vitals.get("temp")
    if temp is not None and (temp < 36.0 or temp > 38.0):
        triggered.append("Temp abnormal")

    return len(triggered), triggered


def _calculate_risk_from_snapshot(vitals: dict, labs: dict) -> dict:
    """Assign a risk tier + probability score based on a snapshot.

    Uses the SAFE proxy criteria from HW7:
      - 0 criteria   → Low      (score 0.05–0.20)
      - 1-2 criteria → Moderate (score 0.30–0.55)
      - 3+ criteria  → High     (score 0.65–0.90)

    TODO: replace with actual deployed ML model inference.
          e.g., model.predict_proba([feature_vector])[0][1]
    """
    import random

    count, triggered = _count_safe_criteria(vitals, labs)

    if count == 0:
        tier = "Low"
        # Small spread within tier — we seed to keep runs consistent per session
        score = round(random.uniform(0.05, 0.20), 2)
    elif count <= 2:
        tier = "Moderate"
        # More criteria → higher within Moderate range
        base = 0.30 + (count - 1) * 0.10
        score = round(base + random.uniform(0.0, 0.10), 2)
    else:
        tier = "High"
        # More criteria → higher within High range
        base = min(0.65 + (count - 3) * 0.06, 0.85)
        score = round(base + random.uniform(0.0, 0.05), 2)

    return {
        "risk_tier": tier,
        "risk_score": score,
        "criteria_count": count,
        "triggered_criteria": triggered,
    }


def _next_patient_id() -> str:
    """Auto-generate the next patient ID (P001, P002, P003, ...)."""
    store = _get_store()
    existing_nums = []
    for p in store:
        pid = p["patient_id"]
        if pid.startswith("P") and pid[1:].isdigit():
            existing_nums.append(int(pid[1:]))
    next_num = (max(existing_nums) + 1) if existing_nums else 1
    return f"P{next_num:03d}"


def admit_patient(name: str, age: int, gender: str, unit: str,
                  vitals: dict, labs: dict) -> dict:
    """Admit a new patient to the ICU.

    Runs the risk calculator on the admission snapshot, assigns a tier,
    inserts into the store, and returns the full patient record including
    the assigned risk tier and score.

    TODO (backend): this becomes a transaction:
      1. INSERT INTO patient (name, age, gender) VALUES (...)
      2. INSERT INTO icu_stay (patient_id, unit, t_admit) VALUES (...)
      3. INSERT INTO hourly_measurement (...) with the admission snapshot
      4. Call model service → INSERT INTO risk_assessment (...)
      5. If risk_tier = High → INSERT INTO alert (...)
    """
    risk = _calculate_risk_from_snapshot(vitals, labs)
    new_patient = {
        "patient_id":  _next_patient_id(),
        "name":        name,
        "age":         int(age),
        "gender":      gender,
        "unit":        unit,
        "icu_hour":    0,
        "risk_tier":   risk["risk_tier"],
        "risk_score":  risk["risk_score"],
        "admitted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "vitals":      dict(vitals),
        "labs":        dict(labs),
        "alert_status": "none",      # ← ADD THIS
        "alert_meta":   None,        # ← ADD THIS
    }
    _get_store().append(new_patient)

    print(f"[MOCK] Admitted {new_patient['patient_id']}: {name} | "
          f"{risk['risk_tier']} ({risk['risk_score']}) | "
          f"{risk['criteria_count']} criteria triggered")

    # Return the full patient dict plus the risk breakdown and tier-transition
    # metadata (matches the shape of recompute_risk_for_patient so the UI
    # dispatcher can handle admit and update the same way).
    return {
        **new_patient,
        "criteria_count":     risk["criteria_count"],
        "triggered_criteria": risk["triggered_criteria"],
        "previous_tier":      None,     # admission has no prior tier
        "tier_changed":       True,     # admission is always a "change" from nothing
    }

# ============================================================
# RISK RECOMPUTATION — used by Update Clinical flow
# ============================================================
def recompute_risk_for_patient(patient_id: str) -> Optional[dict]:
    """Re-run the risk calculator against a patient's current vitals/labs.

    Updates the patient's risk_tier and risk_score in place.
    Clears any prior alert_status (override/acknowledged) because the
    recomputation is a fresh assessment — old responses are stale.

    Returns the event dict, or None if patient not found.
    """
    patient = get_patient_detail(patient_id)
    if patient is None:
        return None

    risk = _calculate_risk_from_snapshot(patient["vitals"], patient["labs"])

    previous_tier = patient["risk_tier"]
    for p in _get_store():
        if p["patient_id"] == patient_id:
            p["risk_tier"]  = risk["risk_tier"]
            p["risk_score"] = risk["risk_score"]
            # Stale — the override/ack was based on earlier data
            p["alert_status"] = "none"
            p["alert_meta"]   = None
            break

    print(f"[MOCK] Recomputed risk for {patient_id}: "
          f"{previous_tier} ({patient['risk_score']}) → "
          f"{risk['risk_tier']} ({risk['risk_score']})")

    return {
        "patient_id":          patient_id,
        "name":                patient["name"],
        "unit":                patient["unit"],
        "risk_tier":           risk["risk_tier"],
        "risk_score":          risk["risk_score"],
        "previous_tier":       previous_tier,
        "tier_changed":        previous_tier != risk["risk_tier"],
        "criteria_count":      risk["criteria_count"],
        "triggered_criteria":  risk["triggered_criteria"],
    }

# ============================================================
# ALERT AUDIT LOGGING — acknowledge + override workflows
# ============================================================
def log_high_risk_acknowledgment(patient_id: str, user_id: int,
                                 selected_interventions: list[str],
                                 notes: str = "") -> bool:
    """Record that a clinician acknowledged a high-risk alert and started
    one or more interventions. Also sets patient's alert_status so the
    dashboard can display an 'Acknowledged' badge.

    TODO: INSERT INTO alert_response (alert_id, user_id, action_type='ACK',
          interventions, notes, t_response) VALUES (...)
    """
    print(f"[AUDIT] {datetime.utcnow().isoformat()} | HIGH-RISK ACK | "
          f"patient={patient_id} | user={user_id} | "
          f"interventions={selected_interventions} | notes={notes!r}")

    # Attach status metadata to the patient record
    for p in _get_store():
        if p["patient_id"] == patient_id:
            p["alert_status"] = "acknowledged"
            p["alert_meta"] = {
                "user_id":       user_id,
                "interventions": list(selected_interventions),
                "notes":         notes,
                "at":            datetime.utcnow().isoformat(),
            }
            return True
    return False


# Allowed categories mirror HW7 part (h)'s structured override taxonomy
OVERRIDE_REASON_CATEGORIES = [
    "False positive",
    "Alternative diagnosis",
    "Already being treated",
    "End-of-life decision",
    "Other",
]


def log_high_risk_override(patient_id: str, user_id: int,
                           reason_category: str, reason_text: str) -> bool:
    """Record that a clinician dismissed/overrode a high-risk alert.
    Sets patient's alert_status for the dashboard 'Overridden' badge.

    The override is a moment-in-time judgment — if the patient's condition
    worsens and risk is recomputed, recompute_risk_for_patient will clear
    this status so the alert can re-fire.

    TODO: INSERT INTO alert_response (alert_id, user_id, action_type='OVERRIDE',
          reason_category, reason_text, t_response) VALUES (...)
    """
    print(f"[AUDIT] {datetime.utcnow().isoformat()} | HIGH-RISK OVERRIDE | "
          f"patient={patient_id} | user={user_id} | "
          f"category={reason_category!r} | reason={reason_text!r}")

    for p in _get_store():
        if p["patient_id"] == patient_id:
            p["alert_status"] = "overridden"
            p["alert_meta"] = {
                "user_id":         user_id,
                "reason_category": reason_category,
                "reason_text":     reason_text,
                "at":              datetime.utcnow().isoformat(),
            }
            return True
    return False

# ============================================================
# ADMIN / POPULATION HEALTH AGGREGATIONS
# ============================================================
# Small-cell suppression threshold — cells with fewer than this many
# patients are withheld from the admin dashboard to protect anonymity.
SUPPRESSION_THRESHOLD = 3


def _age_bin(age: int) -> str:
    """Map an age to one of the HW7 age bins."""
    if age < 40:
        return "<40"
    if age < 55:
        return "40-55"
    if age < 70:
        return "55-70"
    if age < 85:
        return "70-85"
    return "85+"


# Display orders — defined here so charts render consistently
AGE_BIN_ORDER  = ["<40", "40-55", "55-70", "70-85", "85+"]
TIER_ORDER     = ["High", "Moderate", "Low"]
UNIT_ORDER     = ["MICU", "SICU", "CCU", "NICU"]


def get_population_kpis() -> dict:
    """Top-strip KPIs for the admin dashboard.

    TODO: replace each with a real SQL aggregation query.
    """
    patients = _get_store()
    total = len(patients)

    if total == 0:
        return {
            "total_patients":    0,
            "high_risk_count":   0,
            "high_risk_pct":     0.0,
            "avg_risk_score":    0.0,
            "response_rate_pct": 0.0,
            "response_numerator":   0,
            "response_denominator": 0,
        }

    high = [p for p in patients if p["risk_tier"] == "High"]
    high_count = len(high)

    # Response rate = of all currently-high-risk patients, how many have had
    # a clinician response (acknowledge OR override) captured?
    if high_count == 0:
        response_rate = 0.0
        responded = 0
    else:
        responded = sum(
            1 for p in high
            if p.get("alert_status") in ("acknowledged", "overridden")
        )
        response_rate = (responded / high_count) * 100

    return {
        "total_patients":       total,
        "high_risk_count":      high_count,
        "high_risk_pct":        round((high_count / total) * 100, 1),
        "avg_risk_score":       round(
            sum(p["risk_score"] for p in patients) / total, 2),
        "response_rate_pct":    round(response_rate, 1),
        "response_numerator":   responded,
        "response_denominator": high_count,
    }


def get_tier_distribution() -> dict:
    """Counts per tier across all patients, for the donut chart.

    Returns {'tiers': [...], 'counts': [...], 'suppressed': bool,
             'total': int, 'reason': Optional[str]}
    """
    patients = _get_store()
    total = len(patients)

    if total < SUPPRESSION_THRESHOLD:
        return {
            "tiers": [], "counts": [],
            "suppressed": True, "total": total,
            "reason": f"Total patient count ({total}) below "
                      f"privacy threshold (n<{SUPPRESSION_THRESHOLD}).",
        }

    counts = {t: 0 for t in TIER_ORDER}
    for p in patients:
        counts[p["risk_tier"]] = counts.get(p["risk_tier"], 0) + 1

    return {
        "tiers": TIER_ORDER,
        "counts": [counts[t] for t in TIER_ORDER],
        "suppressed": False,
        "total": total,
        "reason": None,
    }


def get_tier_by_age() -> dict:
    """Tier counts broken down by age bin, for the stacked bar chart.

    Returns {'age_bins': [...], 'tiers': [...],
             'matrix': [[int, ...], ...] indexed [age_idx][tier_idx],
             'suppressed_bins': [age_bin, ...]}

    Age bins with fewer than SUPPRESSION_THRESHOLD patients are replaced
    with zeros in the matrix and reported in 'suppressed_bins'.
    """
    patients = _get_store()

    # Initialize matrix: age_bin -> tier -> count
    matrix = {ab: {t: 0 for t in TIER_ORDER} for ab in AGE_BIN_ORDER}
    bin_totals = {ab: 0 for ab in AGE_BIN_ORDER}

    for p in patients:
        ab = _age_bin(p["age"])
        matrix[ab][p["risk_tier"]] += 1
        bin_totals[ab] += 1

    suppressed = [ab for ab, n in bin_totals.items()
                  if 0 < n < SUPPRESSION_THRESHOLD]

    # Zero out suppressed bins in the output
    out_matrix = []
    for ab in AGE_BIN_ORDER:
        if ab in suppressed:
            out_matrix.append([0 for _ in TIER_ORDER])
        else:
            out_matrix.append([matrix[ab][t] for t in TIER_ORDER])

    return {
        "age_bins":        AGE_BIN_ORDER,
        "tiers":           TIER_ORDER,
        "matrix":          out_matrix,
        "suppressed_bins": suppressed,
        "bin_totals":      bin_totals,
    }


def get_tier_by_unit() -> dict:
    """Tier counts broken down by ICU unit, for the horizontal bar chart.

    Same suppression approach as get_tier_by_age but over units.
    """
    patients = _get_store()

    matrix = {u: {t: 0 for t in TIER_ORDER} for u in UNIT_ORDER}
    unit_totals = {u: 0 for u in UNIT_ORDER}

    for p in patients:
        u = p["unit"]
        if u not in matrix:
            # Ignore units we don't display
            continue
        matrix[u][p["risk_tier"]] += 1
        unit_totals[u] += 1

    suppressed = [u for u, n in unit_totals.items()
                  if 0 < n < SUPPRESSION_THRESHOLD]

    out_matrix = []
    for u in UNIT_ORDER:
        if u in suppressed:
            out_matrix.append([0 for _ in TIER_ORDER])
        else:
            out_matrix.append([matrix[u][t] for t in TIER_ORDER])

    return {
        "units":           UNIT_ORDER,
        "tiers":           TIER_ORDER,
        "matrix":          out_matrix,
        "suppressed_units": suppressed,
        "unit_totals":     unit_totals,
    }


def get_alert_response_distribution() -> dict:
    """Breakdown of current high-risk patients by alert response state.

    Categories:
      - Acknowledged: clinician acted on the alert
      - Overridden:   clinician dismissed with structured reason
      - Pending:      alert fired but no clinician response logged yet

    Demonstrates SAFE's structured feedback loop vs Epic ESM's silent
    overrides (referenced in HW7 part d).
    """
    patients = _get_store()
    high = [p for p in patients if p["risk_tier"] == "High"]
    total = len(high)

    if total < SUPPRESSION_THRESHOLD:
        return {
            "categories": [], "counts": [],
            "suppressed": True, "total": total,
            "reason": f"High-risk cohort size ({total}) below "
                      f"privacy threshold (n<{SUPPRESSION_THRESHOLD}).",
        }

    counts = {"Acknowledged": 0, "Overridden": 0, "Pending": 0}
    for p in high:
        status = p.get("alert_status", "none")
        if status == "acknowledged":
            counts["Acknowledged"] += 1
        elif status == "overridden":
            counts["Overridden"] += 1
        else:
            counts["Pending"] += 1

    return {
        "categories": ["Acknowledged", "Overridden", "Pending"],
        "counts":     [counts["Acknowledged"], counts["Overridden"],
                       counts["Pending"]],
        "suppressed": False,
        "total":      total,
        "reason":     None,
    }