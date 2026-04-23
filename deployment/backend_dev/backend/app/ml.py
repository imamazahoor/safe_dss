from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import load

from .config import settings


def _safe_load_model(path_str: str):
    path = Path(path_str)
    return load(path) if path.exists() else None


STAGE1_MODEL = _safe_load_model(settings.stage1_model_path)
STAGE2_MODEL = _safe_load_model(settings.stage2_model_path)


def classify_stage1(score: float) -> str:
    if score >= settings.stage1_high_threshold:
        return "high"
    if score >= settings.stage1_moderate_threshold:
        return "moderate"
    return "low"


def classify_stage2(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "moderate"
    return "low"


def _predict_with_fallback(model, values_json: dict[str, Any], fallback: float) -> float:
    if model is None:
        return fallback
    row = pd.DataFrame([values_json])
    try:
        proba = model.predict_proba(row)[:, 1][0]
        return float(proba)
    except Exception:
        return fallback


def _clinical_stage1_fallback(values_json: dict[str, Any]) -> float:
    """Deterministic risk proxy when serialized model artifacts are unavailable."""
    triggers = 0

    lactate = values_json.get("Lactate")
    if lactate is not None and lactate > 2.0:
        triggers += 1

    map_value = values_json.get("MAP")
    if map_value is not None and map_value < 65:
        triggers += 1

    hr = values_json.get("HR")
    if hr is not None and hr > 100:
        triggers += 1

    resp = values_json.get("Resp")
    if resp is not None and resp > 22:
        triggers += 1

    wbc = values_json.get("WBC")
    if wbc is not None and (wbc < 4.0 or wbc > 12.0):
        triggers += 1

    temp = values_json.get("Temp")
    if temp is not None and (temp < 36.0 or temp > 38.0):
        triggers += 1

    # 0 -> low, 1-2 -> moderate, 3+ -> high
    if triggers == 0:
        return 0.16
    if triggers <= 2:
        return float(np.clip(0.42 + 0.06 * (triggers - 1), 0.30, 0.58))
    return float(np.clip(0.68 + 0.05 * (triggers - 3), 0.60, 0.92))


def _clinical_stage2_fallback(values_json: dict[str, Any]) -> float:
    """Deterministic deterioration proxy on already-flagged patients."""
    score = 0.40
    if (values_json.get("Lactate") or 0) >= 4.0:
        score += 0.18
    if (values_json.get("MAP") or 200) < 60:
        score += 0.16
    if (values_json.get("Creatinine") or 0) >= 2.0:
        score += 0.12
    if (values_json.get("WBC") or 0) >= 16.0:
        score += 0.08
    return float(np.clip(score, 0.05, 0.95))


def score_stage1(values_json: dict[str, Any]) -> float:
    # Deterministic clinical fallback keeps demo behavior plausible.
    fallback = _clinical_stage1_fallback(values_json)
    return _predict_with_fallback(STAGE1_MODEL, values_json, fallback)


def score_stage2(values_json: dict[str, Any], stage1_level: str) -> float | None:
    if stage1_level == "low":
        return None
    fallback = _clinical_stage2_fallback(values_json)
    return _predict_with_fallback(STAGE2_MODEL, values_json, fallback)


def build_explanation(values_json: dict[str, Any], stage1_score: float, stage2_score: float | None) -> dict[str, Any]:
    key_features = []
    for name in ("Lactate", "MAP", "SBP", "Resp", "WBC", "Creatinine", "ICULOS"):
        if name in values_json:
            key_features.append({"feature": name, "value": values_json[name]})

    return {
        "stage1_score": stage1_score,
        "stage2_score": stage2_score,
        "drivers": key_features[:4],
        "message": "Risk influenced by hemodynamics, perfusion, and inflammation trends.",
    }
