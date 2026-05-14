import random
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException
import numpy as np
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .ml import build_explanation, classify_stage1, classify_stage2, score_stage1, score_stage2
from .models import Alert, HourlyMeasurement, ICUStay, Patient, RiskAssessment, User
from .schemas import (
    AlertActionRequest,
    AlertOverrideRequest,
    ICUStayCreate,
    ICUStayOut,
    MeasurementCreate,
    PatientCreate,
    PatientOut,
    RiskAssessmentOut,
)

app = FastAPI(title="SAFE DSS Backend", version="0.1.0")
Base.metadata.create_all(bind=engine)


def _ensure_demo_users(db: Session) -> None:
    """Ensure stable demo users exist for alert actions from Streamlit frontend."""
    if db.query(User).count() == 0:
        db.add_all(
            [
                User(name="Eugene Ho", role="admin"),
                User(name="Dr. Imama Zahoor", role="clinician"),
                User(name="ICU Nurse A", role="nurse"),
            ]
        )
        db.commit()


@app.on_event("startup")
def startup_seed():
    db = SessionLocal()
    try:
        _ensure_demo_users(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/patients", response_model=PatientOut)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    existing = db.query(Patient).filter(Patient.external_patient_id == payload.external_patient_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="external_patient_id already exists")
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@app.get("/patients", response_model=list[PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return db.query(Patient).order_by(Patient.id.desc()).all()


@app.patch("/patients/{external_patient_id}", response_model=PatientOut)
def update_patient(
    external_patient_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    patient = (
        db.query(Patient)
        .filter(Patient.external_patient_id == external_patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    for key in ("name", "age", "gender"):
        if key in payload and payload[key] is not None:
            setattr(patient, key, payload[key])
    db.commit()
    db.refresh(patient)
    return patient


@app.post("/icu-stays", response_model=ICUStayOut)
def create_icu_stay(payload: ICUStayCreate, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    stay = ICUStay(**payload.model_dump())
    db.add(stay)
    db.commit()
    db.refresh(stay)
    return stay


@app.post("/icu-stays/{stay_id}/discharge")
def discharge_icu_stay(stay_id: int, db: Session = Depends(get_db)):
    stay = db.query(ICUStay).filter(ICUStay.id == stay_id).first()
    if not stay:
        raise HTTPException(status_code=404, detail="ICU stay not found")
    stay.discharge_time = datetime.utcnow()
    db.commit()
    return {"status": "ok", "icu_stay_id": stay_id}


@app.post("/measurements/ingest-and-score", response_model=RiskAssessmentOut)
def ingest_and_score(payload: MeasurementCreate, db: Session = Depends(get_db)):
    stay = db.query(ICUStay).filter(ICUStay.id == payload.icu_stay_id).first()
    if not stay:
        raise HTTPException(status_code=404, detail="ICU stay not found")

    measurement = HourlyMeasurement(**payload.model_dump())
    db.add(measurement)
    db.flush()

    s1 = score_stage1(measurement.values_json)
    s1_level = classify_stage1(s1)
    s2 = score_stage2(measurement.values_json, s1_level)
    s2_level = classify_stage2(s2)
    explanation = build_explanation(measurement.values_json, s1, s2)

    risk = RiskAssessment(
        measurement_id=measurement.id,
        stage1_score=s1,
        stage1_level=s1_level,
        stage2_score=s2,
        stage2_level=s2_level,
        explanation_json=explanation,
    )
    db.add(risk)
    db.flush()

    if s1_level == "high":
        db.add(
            Alert(
                risk_assessment_id=risk.id,
                level="high",
                status="pending",
                requires_acknowledgment=True,
            )
        )
    db.commit()
    db.refresh(risk)
    return risk


@app.get("/risk/queue")
def get_risk_queue(level: str | None = None, db: Session = Depends(get_db)):
    q = (
        db.query(RiskAssessment, HourlyMeasurement, ICUStay, Patient)
        .join(HourlyMeasurement, RiskAssessment.measurement_id == HourlyMeasurement.id)
        .join(ICUStay, HourlyMeasurement.icu_stay_id == ICUStay.id)
        .join(Patient, ICUStay.patient_id == Patient.id)
    )
    if level:
        q = q.filter(RiskAssessment.stage1_level == level)
    rows = q.order_by(RiskAssessment.stage1_score.desc()).limit(200).all()
    out = []
    for risk, m, stay, patient in rows:
        out.append(
            {
                "risk_assessment_id": risk.id,
                "patient_id": patient.id,
                "external_patient_id": patient.external_patient_id,
                "patient_name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
                "unit_type": stay.unit_type,
                "measurement_time": m.measurement_time,
                "stage1_score": risk.stage1_score,
                "stage1_level": risk.stage1_level,
                "stage2_score": risk.stage2_score,
                "stage2_level": risk.stage2_level,
            }
        )
    return out


@app.get("/patients/{external_patient_id}/snapshot")
def patient_snapshot(external_patient_id: str, db: Session = Depends(get_db)):
    row = (
        db.query(RiskAssessment, HourlyMeasurement, ICUStay, Patient)
        .join(HourlyMeasurement, RiskAssessment.measurement_id == HourlyMeasurement.id)
        .join(ICUStay, HourlyMeasurement.icu_stay_id == ICUStay.id)
        .join(Patient, ICUStay.patient_id == Patient.id)
        .filter(Patient.external_patient_id == external_patient_id)
        .order_by(HourlyMeasurement.measurement_time.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Patient snapshot not found")

    risk, m, stay, patient = row
    latest_alert = (
        db.query(Alert)
        .filter(Alert.risk_assessment_id == risk.id)
        .order_by(Alert.created_at.desc())
        .first()
    )
    return {
        "patient_db_id": patient.id,
        "external_patient_id": patient.external_patient_id,
        "patient_name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "icu_stay_id": stay.id,
        "unit_type": stay.unit_type,
        "admit_time": stay.admit_time,
        "measurement_time": m.measurement_time,
        "values_json": m.values_json,
        "stage1_score": risk.stage1_score,
        "stage1_level": risk.stage1_level,
        "stage2_score": risk.stage2_score,
        "stage2_level": risk.stage2_level,
        "explanation_json": risk.explanation_json,
        "latest_alert": (
            {
                "alert_id": latest_alert.id,
                "status": latest_alert.status,
                "action_type": latest_alert.action_type,
                "notes": latest_alert.notes,
            }
            if latest_alert
            else None
        ),
    }


@app.get("/patients/{external_patient_id}/risk-history")
def patient_risk_history(
    external_patient_id: str,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(RiskAssessment, HourlyMeasurement, ICUStay, Patient)
        .join(HourlyMeasurement, RiskAssessment.measurement_id == HourlyMeasurement.id)
        .join(ICUStay, HourlyMeasurement.icu_stay_id == ICUStay.id)
        .join(Patient, ICUStay.patient_id == Patient.id)
        .filter(Patient.external_patient_id == external_patient_id)
        .filter(HourlyMeasurement.measurement_time >= since)
        .order_by(HourlyMeasurement.measurement_time.asc())
        .all()
    )
    return [
        {
            "measurement_time": m.measurement_time,
            "stage1_score": risk.stage1_score,
            "stage1_level": risk.stage1_level,
        }
        for risk, m, _stay, _patient in rows
    ]


@app.get("/patients/{external_patient_id}/alerts/latest")
def latest_alert_for_patient(
    external_patient_id: str,
    level: str | None = "high",
    status: str | None = "pending",
    db: Session = Depends(get_db),
):
    q = (
        db.query(Alert, RiskAssessment, HourlyMeasurement, ICUStay, Patient)
        .join(RiskAssessment, Alert.risk_assessment_id == RiskAssessment.id)
        .join(HourlyMeasurement, RiskAssessment.measurement_id == HourlyMeasurement.id)
        .join(ICUStay, HourlyMeasurement.icu_stay_id == ICUStay.id)
        .join(Patient, ICUStay.patient_id == Patient.id)
        .filter(Patient.external_patient_id == external_patient_id)
    )
    if level:
        q = q.filter(Alert.level == level)
    if status:
        q = q.filter(Alert.status == status)
    row = q.order_by(Alert.created_at.desc()).first()
    if not row:
        raise HTTPException(status_code=404, detail="No matching alert found")
    alert, risk, _m, _stay, _patient = row
    return {
        "alert_id": alert.id,
        "status": alert.status,
        "level": alert.level,
        "risk_assessment_id": risk.id,
    }


@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, payload: AlertActionRequest, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        _ensure_demo_users(db)
    alert.status = "acknowledged"
    alert.acted_at = datetime.utcnow()
    alert.acted_by_user_id = payload.user_id
    alert.action_type = "acknowledge_and_act"
    alert.notes = payload.notes
    alert.interventions_json = payload.interventions_json
    db.commit()
    return {"status": "ok", "alert_id": alert_id}


@app.post("/alerts/{alert_id}/override")
def override_alert(alert_id: int, payload: AlertOverrideRequest, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        _ensure_demo_users(db)
    alert.status = "overridden"
    alert.acted_at = datetime.utcnow()
    alert.acted_by_user_id = payload.user_id
    alert.action_type = "override"
    alert.override_reason = payload.override_reason
    alert.notes = payload.notes
    db.commit()
    return {"status": "ok", "alert_id": alert_id}


@app.get("/admin/dashboard/summary")
def admin_summary(db: Session = Depends(get_db)):
    total = db.query(RiskAssessment.id).count()
    by_level = (
        db.query(RiskAssessment.stage1_level, func.count(RiskAssessment.id))
        .group_by(RiskAssessment.stage1_level)
        .all()
    )
    pending_alerts = db.query(Alert.id).filter(Alert.status == "pending").count()
    return {
        "total_assessments": total,
        "risk_breakdown": {level: n for level, n in by_level},
        "pending_high_alerts": pending_alerts,
    }


@app.get("/admin/dashboard/risk-distribution")
def admin_risk_distribution(db: Session = Depends(get_db)):
    rows = (
        db.query(RiskAssessment.stage1_level, func.count(RiskAssessment.id).label("count"))
        .group_by(RiskAssessment.stage1_level)
        .all()
    )
    return [{"risk_level": level, "count": n} for level, n in rows]


@app.get("/admin/dashboard/trends")
def admin_trends(db: Session = Depends(get_db)):
    rows = (
        db.query(func.date(RiskAssessment.predicted_at).label("day"), func.count(RiskAssessment.id).label("count"))
        .group_by(func.date(RiskAssessment.predicted_at))
        .order_by(func.date(RiskAssessment.predicted_at))
        .all()
    )
    return [{"day": str(day), "count": count} for day, count in rows]


@app.get("/admin/dashboard/demographics")
def admin_demographics(db: Session = Depends(get_db)):
    age_bucket = case(
        (Patient.age < 40, "<40"),
        (Patient.age < 60, "40-59"),
        (Patient.age < 80, "60-79"),
        else_="80+",
    )
    rows = (
        db.query(age_bucket.label("age_group"), RiskAssessment.stage1_level, func.count(RiskAssessment.id))
        .join(ICUStay, ICUStay.patient_id == Patient.id)
        .join(HourlyMeasurement, HourlyMeasurement.icu_stay_id == ICUStay.id)
        .join(RiskAssessment, RiskAssessment.measurement_id == HourlyMeasurement.id)
        .group_by(age_bucket, RiskAssessment.stage1_level)
        .all()
    )
    return [{"age_group": age_group, "risk_level": level, "count": count} for age_group, level, count in rows]


@app.get("/admin/dashboard/alerts-performance")
def admin_alerts_performance(db: Session = Depends(get_db)):
    rows = db.query(Alert.status, func.count(Alert.id)).group_by(Alert.status).all()
    return [{"status": status, "count": count} for status, count in rows]


@app.post("/seed/demo-data")
def seed_demo_data(
    n_patients: int = 40,
    hours_per_patient: int = 24,
    db: Session = Depends(get_db),
):
    if n_patients < 1 or hours_per_patient < 1:
        raise HTTPException(status_code=400, detail="n_patients and hours_per_patient must be >= 1")

    users = db.query(User).all()
    if not users:
        users = [
            User(name="ICU Nurse A", role="nurse"),
            User(name="Physician B", role="physician"),
            User(name="Admin C", role="admin"),
        ]
        db.add_all(users)
        db.flush()

    created = {"patients": 0, "stays": 0, "measurements": 0, "risk_assessments": 0, "alerts": 0}

    unit_types = ["MICU", "SICU", "CCU", "NeuroICU"]
    genders = ["F", "M"]

    for p_idx in range(n_patients):
        ext_id = f"DEMO-{int(datetime.utcnow().timestamp())}-{p_idx}"
        patient = Patient(
            external_patient_id=ext_id,
            name=f"Demo Patient {p_idx + 1}",
            age=random.randint(22, 92),
            gender=random.choice(genders),
        )
        db.add(patient)
        db.flush()
        created["patients"] += 1

        admit_base = datetime.utcnow() - timedelta(days=random.randint(1, 30))
        stay = ICUStay(
            patient_id=patient.id,
            unit_type=random.choice(unit_types),
            admit_time=admit_base,
            discharge_time=admit_base + timedelta(hours=hours_per_patient + random.randint(6, 36)),
        )
        db.add(stay)
        db.flush()
        created["stays"] += 1

        baseline_risk_shift = random.uniform(-0.08, 0.12)

        for h in range(hours_per_patient):
            t = admit_base + timedelta(hours=h)
            shock_window = h > int(0.65 * hours_per_patient)
            values = {
                "ICULOS": h + 1,
                "HR": float(np.clip(random.gauss(92, 15) + (12 if shock_window else 0), 45, 180)),
                "MAP": float(np.clip(random.gauss(73, 10) - (10 if shock_window else 0), 35, 120)),
                "SBP": float(np.clip(random.gauss(112, 18) - (14 if shock_window else 0), 60, 220)),
                "Resp": float(np.clip(random.gauss(20, 4) + (4 if shock_window else 0), 8, 45)),
                "Temp": float(np.clip(random.gauss(37.1, 0.8), 34.0, 41.0)),
                "WBC": float(np.clip(random.gauss(10.5, 3.2) + (2 if shock_window else 0), 1.0, 35.0)),
                "Lactate": float(np.clip(random.gauss(1.9, 0.7) + (1.3 if shock_window else 0), 0.4, 8.0)),
                "Creatinine": float(np.clip(random.gauss(1.2, 0.5) + (0.4 if shock_window else 0), 0.3, 7.0)),
                "Platelets": float(np.clip(random.gauss(220, 75) - (20 if shock_window else 0), 20, 500)),
                "FiO2": float(np.clip(random.gauss(0.35, 0.1) + (0.12 if shock_window else 0), 0.21, 1.0)),
            }
            sepsis_label = 1 if (shock_window and random.random() < 0.28) else 0
            measurement = HourlyMeasurement(
                icu_stay_id=stay.id,
                measurement_time=t,
                sepsis_label=sepsis_label,
                values_json=values,
            )
            db.add(measurement)
            db.flush()
            created["measurements"] += 1

            s1 = float(np.clip(score_stage1(values) + baseline_risk_shift, 0.01, 0.99))
            s1_level = classify_stage1(s1)
            s2 = score_stage2(values, s1_level)
            s2 = float(np.clip((s2 if s2 is not None else 0.0) + (0.08 if shock_window and s1_level != "low" else 0.0), 0.01, 0.99)) if s2 is not None else None
            s2_level = classify_stage2(s2)
            explanation = build_explanation(values, s1, s2)

            risk = RiskAssessment(
                measurement_id=measurement.id,
                stage1_score=s1,
                stage1_level=s1_level,
                stage2_score=s2,
                stage2_level=s2_level,
                explanation_json=explanation,
            )
            db.add(risk)
            db.flush()
            created["risk_assessments"] += 1

            if s1_level == "high":
                action_roll = random.random()
                if action_roll < 0.55:
                    status = "acknowledged"
                    action_type = "acknowledge_and_act"
                    override_reason = None
                elif action_roll < 0.8:
                    status = "overridden"
                    action_type = "override"
                    override_reason = random.choice(
                        ["false_positive", "alternative_diagnosis", "already_treated", "other"]
                    )
                else:
                    status = "pending"
                    action_type = None
                    override_reason = None

                chosen_user = random.choice(users)
                alert = Alert(
                    risk_assessment_id=risk.id,
                    level="high",
                    status=status,
                    created_at=t,
                    acted_at=(t + timedelta(minutes=random.randint(3, 45))) if status != "pending" else None,
                    acted_by_user_id=chosen_user.id if status != "pending" else None,
                    action_type=action_type,
                    override_reason=override_reason,
                    notes="Demo seeded alert action",
                    interventions_json={"bundle_started": status == "acknowledged"},
                    requires_acknowledgment=True,
                )
                db.add(alert)
                created["alerts"] += 1

    db.commit()
    return {"status": "ok", "created": created}
