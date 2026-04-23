"""
SAFE Data Service
-----------------
UI-facing service layer backed by SAFE FastAPI.
Function signatures remain stable so Streamlit screens stay unchanged.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Any

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("SAFE_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT_S = 12


_DEMO_USERS = {
    "admin": {
        "user_id": 1,
        "username": "admin",
        "password": "demo",
        "name": "Eugene Ho",
        "role": "admin",
    },
    "clinician": {
        "user_id": 2,
        "username": "clinician",
        "password": "demo",
        "name": "Dr. Imama Zahoor",
        "role": "clinician",
    },
}

OVERRIDE_REASON_CATEGORIES = [
    "False positive",
    "Alternative diagnosis",
    "Already being treated",
    "End-of-life decision",
    "Other",
]

SUPPRESSION_THRESHOLD = 3
AGE_BIN_ORDER = ["<40", "40-55", "55-70", "70-85", "85+"]
TIER_ORDER = ["High", "Moderate", "Low"]
UNIT_ORDER = ["MICU", "SICU", "CCU", "NICU"]


def _api(method: str, path: str, payload: dict | None = None, params: dict | None = None) -> Any:
    url = f"{API_BASE_URL}{path}"
    try:
        response = requests.request(
            method=method,
            url=url,
            json=payload,
            params=params,
            timeout=REQUEST_TIMEOUT_S,
        )
    except requests.RequestException:
        return None
    if not response.ok:
        return None
    if not response.text:
        return {}
    try:
        return response.json()
    except ValueError:
        return None


def _title_tier(level: str | None) -> str:
    m = {"high": "High", "moderate": "Moderate", "low": "Low"}
    return m.get((level or "").lower(), "Low")


def _lower_tier(level: str | None) -> str:
    if not level:
        return "low"
    return level.lower()


def _to_backend_values(vitals: dict, labs: dict, icu_hour: int = 0) -> dict:
    return {
        "ICULOS": int(icu_hour),
        "HR": vitals.get("hr"),
        "MAP": vitals.get("map"),
        "SBP": vitals.get("sbp"),
        "Resp": vitals.get("resp"),
        "Temp": vitals.get("temp"),
        "O2Sat": vitals.get("o2sat"),
        "Lactate": labs.get("lactate"),
        "WBC": labs.get("wbc"),
        "Creatinine": labs.get("creatinine"),
        "Platelets": labs.get("platelets"),
        "BUN": labs.get("bun"),
        "Glucose": labs.get("glucose"),
    }


def _to_vitals(values: dict | None) -> dict:
    values = values or {}
    return {
        "hr": values.get("HR", 0.0),
        "map": values.get("MAP", 0.0),
        "sbp": values.get("SBP", 0.0),
        "temp": values.get("Temp", 0.0),
        "resp": values.get("Resp", 0.0),
        "o2sat": values.get("O2Sat", 0.0),
    }


def _to_labs(values: dict | None) -> dict:
    values = values or {}
    return {
        "lactate": values.get("Lactate", 0.0),
        "wbc": values.get("WBC", 0.0),
        "creatinine": values.get("Creatinine", 0.0),
        "platelets": values.get("Platelets", 0.0),
        "bun": values.get("BUN", 0.0),
        "glucose": values.get("Glucose", 0.0),
    }


def _get_event_cache() -> dict:
    return st.session_state.setdefault("_last_risk_event_by_patient", {})


def _get_locally_discharged_ids() -> set[str]:
    """Track discharged patients client-side so queue updates are immediate."""
    return st.session_state.setdefault("_locally_discharged_patient_ids", set())


def _is_active_snapshot(snapshot: dict | None) -> bool:
    """An ICU stay is active only when no discharge timestamp is present."""
    if not snapshot:
        return False
    return snapshot.get("discharge_time") is None


def _build_event_from_snapshot(snapshot: dict, previous_tier: str | None = None) -> dict:
    drivers = (snapshot.get("explanation_json") or {}).get("drivers", [])
    return {
        "patient_id": snapshot["external_patient_id"],
        "name": snapshot["patient_name"],
        "unit": snapshot.get("unit_type") or "ICU",
        "risk_tier": _title_tier(snapshot.get("stage1_level")),
        "risk_score": float(snapshot.get("stage1_score") or 0.0),
        "previous_tier": previous_tier,
        "tier_changed": previous_tier is None or previous_tier != _title_tier(snapshot.get("stage1_level")),
        "criteria_count": len(drivers),
        "triggered_criteria": [d.get("feature", "Driver") for d in drivers],
    }


def authenticate_user(username: str, password: str, selected_role: str) -> Optional[dict]:
    user = _DEMO_USERS.get(username.strip().lower())
    if user is None or user["password"] != password or user["role"] != selected_role:
        return None
    return {k: v for k, v in user.items() if k != "password"}


def log_login_attempt(username: str, success: bool, role: str) -> None:
    status = "SUCCESS" if success else "FAILURE"
    print(f"[AUDIT] {datetime.utcnow().isoformat()} | LOGIN {status} | user={username} | role={role}")


def get_dashboard_stats() -> dict:
    rows = _api("GET", "/risk/queue") or []
    discharged_ids = _get_locally_discharged_ids()
    by_external = {}
    for row in rows:
        external_id = row.get("external_patient_id")
        if not external_id or external_id in discharged_ids:
            continue
        by_external[external_id] = row
    patients = list(by_external.values())
    total = len(patients)
    high = sum(1 for p in patients if _lower_tier(p.get("stage1_level")) == "high")
    avg = (sum(float(p.get("stage1_score") or 0.0) for p in patients) / total) if total else 0.0
    return {
        "total_patients": total,
        "high_risk_alerts": high,
        "avg_risk_score": round(avg, 2),
    }


def get_active_patients() -> pd.DataFrame:
    all_patients = get_patients_by_tier("High") + get_patients_by_tier("Moderate") + get_patients_by_tier("Low")
    return pd.DataFrame(all_patients)


def get_patients_by_tier(tier: str) -> list[dict]:
    rows = _api("GET", "/risk/queue", params={"level": _lower_tier(tier)}) or []
    discharged_ids = _get_locally_discharged_ids()
    out = []
    seen = set()
    target_tier = (tier or "Low").strip().title()
    for row in rows:
        external_id = row.get("external_patient_id")
        if not external_id or external_id in seen or external_id in discharged_ids:
            continue
        snapshot = _api("GET", f"/patients/{external_id}/snapshot")
        if not _is_active_snapshot(snapshot):
            continue
        actual_tier = _title_tier(snapshot.get("stage1_level"))
        # Defensive client-side filter: backend queue endpoint can return mixed tiers.
        if actual_tier != target_tier:
            continue
        seen.add(external_id)
        alert = snapshot.get("latest_alert") or {}
        status = alert.get("status", "none")
        out.append(
            {
                "patient_id": external_id,
                "name": snapshot["patient_name"],
                "age": snapshot["age"],
                "gender": snapshot["gender"],
                "unit": snapshot.get("unit_type") or "ICU",
                "icu_hour": int((snapshot.get("values_json") or {}).get("ICULOS", 0)),
                "risk_tier": actual_tier,
                "risk_score": float(snapshot.get("stage1_score") or 0.0),
                "admitted_at": str(snapshot.get("admit_time", ""))[:16].replace("T", " "),
                "vitals": _to_vitals(snapshot.get("values_json")),
                "labs": _to_labs(snapshot.get("values_json")),
                "alert_status": status if status in ("acknowledged", "overridden", "pending") else "none",
                "alert_meta": alert or None,
            }
        )
    out.sort(key=lambda p: p["risk_score"], reverse=True)
    return out


def get_patient_detail(patient_id: str) -> Optional[dict]:
    snapshot = _api("GET", f"/patients/{patient_id}/snapshot")
    if not snapshot:
        return None
    alert = snapshot.get("latest_alert") or {}
    status = alert.get("status", "none")
    return {
        "patient_id": patient_id,
        "name": snapshot["patient_name"],
        "age": snapshot["age"],
        "gender": snapshot["gender"],
        "unit": snapshot.get("unit_type") or "ICU",
        "icu_hour": int((snapshot.get("values_json") or {}).get("ICULOS", 0)),
        "risk_tier": _title_tier(snapshot.get("stage1_level")),
        "risk_score": float(snapshot.get("stage1_score") or 0.0),
        "admitted_at": str(snapshot.get("admit_time", ""))[:16].replace("T", " "),
        "vitals": _to_vitals(snapshot.get("values_json")),
        "labs": _to_labs(snapshot.get("values_json")),
        "alert_status": status if status in ("acknowledged", "overridden", "pending") else "none",
        "alert_meta": alert or None,
    }


def update_patient_profile(patient_id: str, updates: dict) -> bool:
    payload = {k: updates.get(k) for k in ("name", "age", "gender") if k in updates}
    result = _api("PATCH", f"/patients/{patient_id}", payload=payload)
    return bool(result)


def record_new_measurement(patient_id: str, vitals: dict, labs: dict) -> bool:
    snapshot = _api("GET", f"/patients/{patient_id}/snapshot")
    if not snapshot:
        return False
    previous_tier = _title_tier(snapshot.get("stage1_level"))
    values = _to_backend_values(vitals, labs, icu_hour=int((snapshot.get("values_json") or {}).get("ICULOS", 0)) + 1)
    created = _api(
        "POST",
        "/measurements/ingest-and-score",
        payload={
            "icu_stay_id": snapshot["icu_stay_id"],
            "measurement_time": datetime.utcnow().isoformat(),
            "sepsis_label": None,
            "values_json": values,
        },
    )
    if not created:
        return False
    updated_snapshot = _api("GET", f"/patients/{patient_id}/snapshot")
    if not updated_snapshot:
        return False
    event = _build_event_from_snapshot(updated_snapshot, previous_tier=previous_tier)
    _get_event_cache()[patient_id] = event
    return True


def discharge_patient(patient_id: str) -> bool:
    snapshot = _api("GET", f"/patients/{patient_id}/snapshot")
    if not snapshot:
        return False
    result = _api("POST", f"/icu-stays/{snapshot['icu_stay_id']}/discharge")
    succeeded = bool(result)
    if succeeded:
        _get_locally_discharged_ids().add(patient_id)
    return succeeded


def get_pending_alerts() -> pd.DataFrame:
    rows = _api("GET", "/risk/queue", params={"level": "high"}) or []
    out = []
    for row in rows:
        external_id = row.get("external_patient_id")
        if not external_id:
            continue
        alert = _api("GET", f"/patients/{external_id}/alerts/latest", params={"level": "high", "status": "pending"})
        if not alert:
            continue
        out.append(
            {
                "alert_id": alert["alert_id"],
                "patient_id": external_id,
                "alert_level": "High",
                "risk_score": float(row.get("stage1_score") or 0.0),
                "triggered_at": row.get("measurement_time"),
                "status": "Pending",
            }
        )
    return pd.DataFrame(out)


def record_alert_response(alert_id: int, user_id: int, action: str, notes: str = "") -> bool:
    if action == "acknowledge_and_act":
        payload = {"user_id": user_id, "notes": notes, "interventions_json": {}}
        res = _api("POST", f"/alerts/{alert_id}/acknowledge", payload=payload)
    else:
        payload = {"user_id": user_id, "override_reason": "Other", "notes": notes}
        res = _api("POST", f"/alerts/{alert_id}/override", payload=payload)
    return bool(res)


_UNIT_MAP = {
    "Heart rate": "bpm",
    "MAP": "mmHg",
    "SBP": "mmHg",
    "Resp": "/min",
    "WBC": "x10⁹/L",
    "Lactate": "mmol/L",
    "Creatinine": "mg/dL",
    "Platelets": "x10⁹/L",
    "ICULOS": "hr",
}


def get_risk_explanation(patient_id: str, top_n: int = 5) -> list[dict]:
    snapshot = _api("GET", f"/patients/{patient_id}/snapshot")
    if not snapshot:
        return []
    drivers = (snapshot.get("explanation_json") or {}).get("drivers", [])
    out = []
    for idx, d in enumerate(drivers[:top_n]):
        value = d.get("value")
        out.append(
            {
                "name": d.get("feature", "Feature"),
                "value": value,
                "unit": _UNIT_MAP.get(d.get("feature", ""), ""),
                "direction": "up",
                "status": "elevated",
                "contribution": round(max(0.05, 0.35 - idx * 0.06), 2),
            }
        )
    return out


def get_risk_history(patient_id: str, hours: int = 24) -> pd.DataFrame:
    rows = _api("GET", f"/patients/{patient_id}/risk-history", params={"hours": hours}) or []
    if not rows:
        current = get_patient_detail(patient_id)
        if current is None:
            return pd.DataFrame(columns=["hour", "risk_score"])
        return pd.DataFrame({"hour": [0], "risk_score": [current["risk_score"]]})
    frame = pd.DataFrame(rows)
    frame["measurement_time"] = pd.to_datetime(frame["measurement_time"], errors="coerce")
    tmax = frame["measurement_time"].max()
    frame["hour"] = ((frame["measurement_time"] - tmax).dt.total_seconds() / 3600.0).round().astype(int)
    frame = frame.rename(columns={"stage1_score": "risk_score"})
    return frame[["hour", "risk_score"]]


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
    return list(_RECOMMENDATIONS_BY_TIER.get(risk_tier, []))


def confirm_risk_classification(patient_id: str, user_id: int) -> bool:
    print(f"[AUDIT] {datetime.utcnow().isoformat()} | CONFIRM | patient={patient_id} | user={user_id}")
    return True


def reclassify_patient(patient_id: str, new_tier: str, user_id: int, reason: str = "") -> bool:
    print(
        f"[AUDIT] {datetime.utcnow().isoformat()} | RECLASSIFY | "
        f"patient={patient_id} | user={user_id} | tier={new_tier} | reason={reason!r}"
    )
    return True


def _next_external_patient_id() -> str:
    patients = _api("GET", "/patients") or []
    nums = []
    for p in patients:
        ext = p.get("external_patient_id", "")
        if ext.startswith("P") and ext[1:].isdigit():
            nums.append(int(ext[1:]))
    nxt = max(nums) + 1 if nums else 1
    return f"P{nxt:03d}"


def admit_patient(name: str, age: int, gender: str, unit: str, vitals: dict, labs: dict) -> dict:
    external_id = _next_external_patient_id()
    patient = _api(
        "POST",
        "/patients",
        payload={
            "external_patient_id": external_id,
            "name": name,
            "age": int(age),
            "gender": gender,
        },
    )
    if not patient:
        raise RuntimeError("Failed to create patient")
    stay = _api(
        "POST",
        "/icu-stays",
        payload={
            "patient_id": patient["id"],
            "unit_type": unit,
            "admit_time": datetime.utcnow().isoformat(),
            "discharge_time": None,
        },
    )
    if not stay:
        raise RuntimeError("Failed to create ICU stay")
    values = _to_backend_values(vitals, labs, icu_hour=0)
    scored = _api(
        "POST",
        "/measurements/ingest-and-score",
        payload={
            "icu_stay_id": stay["id"],
            "measurement_time": datetime.utcnow().isoformat(),
            "sepsis_label": None,
            "values_json": values,
        },
    )
    if not scored:
        raise RuntimeError("Failed to score admission measurement")
    snapshot = _api("GET", f"/patients/{external_id}/snapshot")
    if not snapshot:
        raise RuntimeError("Failed to fetch admission snapshot")
    event = _build_event_from_snapshot(snapshot, previous_tier=None)
    _get_event_cache()[external_id] = event
    return event


def recompute_risk_for_patient(patient_id: str) -> Optional[dict]:
    cached = _get_event_cache().pop(patient_id, None)
    if cached:
        return cached
    snapshot = _api("GET", f"/patients/{patient_id}/snapshot")
    if not snapshot:
        return None
    return _build_event_from_snapshot(snapshot, previous_tier=None)


def log_high_risk_acknowledgment(
    patient_id: str,
    user_id: int,
    selected_interventions: list[str],
    notes: str = "",
) -> bool:
    alert = _api(
        "GET",
        f"/patients/{patient_id}/alerts/latest",
        params={"level": "high", "status": "pending"},
    )
    if not alert:
        return False
    res = _api(
        "POST",
        f"/alerts/{alert['alert_id']}/acknowledge",
        payload={
            "user_id": user_id,
            "notes": notes,
            "interventions_json": {"items": list(selected_interventions)},
        },
    )
    return bool(res)


def log_high_risk_override(patient_id: str, user_id: int, reason_category: str, reason_text: str) -> bool:
    alert = _api(
        "GET",
        f"/patients/{patient_id}/alerts/latest",
        params={"level": "high", "status": "pending"},
    )
    if not alert:
        return False
    res = _api(
        "POST",
        f"/alerts/{alert['alert_id']}/override",
        payload={
            "user_id": user_id,
            "override_reason": reason_category,
            "notes": reason_text,
        },
    )
    return bool(res)


def _age_bin(age: int) -> str:
    if age < 40:
        return "<40"
    if age < 55:
        return "40-55"
    if age < 70:
        return "55-70"
    if age < 85:
        return "70-85"
    return "85+"


def get_population_kpis() -> dict:
    summary = _api("GET", "/admin/dashboard/summary") or {}
    queue = _api("GET", "/risk/queue") or []
    alert_perf = _api("GET", "/admin/dashboard/alerts-performance") or []
    by_external = {}
    for row in queue:
        by_external[row.get("external_patient_id")] = row
    patients = list(by_external.values())
    total = len(patients)
    high_count = sum(1 for p in patients if _lower_tier(p.get("stage1_level")) == "high")
    avg = (sum(float(p.get("stage1_score") or 0.0) for p in patients) / total) if total else 0.0

    # Compute response rate from alert workflow states (source of truth),
    # not queue size deltas.
    acknowledged = 0
    pending = 0
    overridden = 0
    for row in alert_perf:
        status = (row.get("status") or "").lower()
        count = int(row.get("count", 0))
        if status == "acknowledged":
            acknowledged += count
        elif status == "pending":
            pending += count
        elif status == "overridden":
            overridden += count

    # "Alert response rate" is specifically acknowledged high-risk alerts.
    # Denominator uses all tracked high-risk alert outcomes.
    response_denominator = acknowledged + pending + overridden
    response_numerator = acknowledged
    response_rate = (
        response_numerator / response_denominator * 100
        if response_denominator
        else 0.0
    )
    return {
        "total_patients": total,
        "high_risk_count": high_count,
        "high_risk_pct": round((high_count / total) * 100, 1) if total else 0.0,
        "avg_risk_score": round(avg, 2),
        "response_rate_pct": round(response_rate, 1),
        "response_numerator": response_numerator,
        "response_denominator": response_denominator,
    }


def get_tier_distribution() -> dict:
    rows = _api("GET", "/admin/dashboard/risk-distribution") or []
    counts = {"High": 0, "Moderate": 0, "Low": 0}
    for r in rows:
        counts[_title_tier(r.get("risk_level"))] = int(r.get("count", 0))
    total = sum(counts.values())
    if total < SUPPRESSION_THRESHOLD:
        return {
            "tiers": [],
            "counts": [],
            "suppressed": True,
            "total": total,
            "reason": f"Total patient count ({total}) below privacy threshold (n<{SUPPRESSION_THRESHOLD}).",
        }
    return {
        "tiers": TIER_ORDER,
        "counts": [counts[t] for t in TIER_ORDER],
        "suppressed": False,
        "total": total,
        "reason": None,
    }


def get_tier_by_age() -> dict:
    rows = _api("GET", "/admin/dashboard/demographics") or []
    matrix = {ab: {t: 0 for t in TIER_ORDER} for ab in AGE_BIN_ORDER}
    bin_totals = {ab: 0 for ab in AGE_BIN_ORDER}
    for r in rows:
        raw = (r.get("age_group") or "").strip()
        mapped_age = {"40-59": "40-55", "60-79": "55-70", "80+": "85+"}.get(raw, raw)
        if mapped_age not in matrix:
            continue
        tier = _title_tier(r.get("risk_level"))
        count = int(r.get("count", 0))
        matrix[mapped_age][tier] += count
        bin_totals[mapped_age] += count
    suppressed = [ab for ab, n in bin_totals.items() if 0 < n < SUPPRESSION_THRESHOLD]
    out_matrix = []
    for ab in AGE_BIN_ORDER:
        if ab in suppressed:
            out_matrix.append([0 for _ in TIER_ORDER])
        else:
            out_matrix.append([matrix[ab][t] for t in TIER_ORDER])
    return {
        "age_bins": AGE_BIN_ORDER,
        "tiers": TIER_ORDER,
        "matrix": out_matrix,
        "suppressed_bins": suppressed,
        "bin_totals": bin_totals,
    }


def get_tier_by_unit() -> dict:
    rows = _api("GET", "/risk/queue") or []
    latest = {}
    for r in rows:
        latest[r.get("external_patient_id")] = r
    matrix = {u: {t: 0 for t in TIER_ORDER} for u in UNIT_ORDER}
    unit_totals = {u: 0 for u in UNIT_ORDER}
    for row in latest.values():
        unit = row.get("unit_type")
        if unit not in matrix:
            continue
        tier = _title_tier(row.get("stage1_level"))
        matrix[unit][tier] += 1
        unit_totals[unit] += 1
    suppressed = [u for u, n in unit_totals.items() if 0 < n < SUPPRESSION_THRESHOLD]
    out_matrix = []
    for u in UNIT_ORDER:
        if u in suppressed:
            out_matrix.append([0 for _ in TIER_ORDER])
        else:
            out_matrix.append([matrix[u][t] for t in TIER_ORDER])
    return {
        "units": UNIT_ORDER,
        "tiers": TIER_ORDER,
        "matrix": out_matrix,
        "suppressed_units": suppressed,
        "unit_totals": unit_totals,
    }


def get_alert_response_distribution() -> dict:
    rows = _api("GET", "/admin/dashboard/alerts-performance") or []
    counts = {"Acknowledged": 0, "Overridden": 0, "Pending": 0}
    for r in rows:
        status = (r.get("status") or "").lower()
        n = int(r.get("count", 0))
        if status == "acknowledged":
            counts["Acknowledged"] += n
        elif status == "overridden":
            counts["Overridden"] += n
        elif status == "pending":
            counts["Pending"] += n
    total = sum(counts.values())
    if total < SUPPRESSION_THRESHOLD:
        return {
            "categories": [],
            "counts": [],
            "suppressed": True,
            "total": total,
            "reason": f"High-risk cohort size ({total}) below privacy threshold (n<{SUPPRESSION_THRESHOLD}).",
        }
    return {
        "categories": ["Acknowledged", "Overridden", "Pending"],
        "counts": [counts["Acknowledged"], counts["Overridden"], counts["Pending"]],
        "suppressed": False,
        "total": total,
        "reason": None,
    }
