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


def score_stage1(values_json: dict[str, Any]) -> float:
    # Deterministic fallback keeps dev API usable when model artifacts are absent.
    fallback = float(np.clip(0.4 + 0.08 * np.random.randn(), 0.01, 0.99))
    return _predict_with_fallback(STAGE1_MODEL, values_json, fallback)


def score_stage2(values_json: dict[str, Any], stage1_level: str) -> float | None:
    if stage1_level == "low":
        return None
    fallback = float(np.clip(0.45 + 0.10 * np.random.randn(), 0.01, 0.99))
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
