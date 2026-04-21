from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    external_patient_id: str
    name: str
    age: int = Field(gt=0)
    gender: str


class PatientOut(BaseModel):
    id: int
    external_patient_id: str
    name: str
    age: int
    gender: str

    class Config:
        from_attributes = True


class ICUStayCreate(BaseModel):
    patient_id: int
    unit_type: str | None = None
    admit_time: datetime
    discharge_time: datetime | None = None


class ICUStayOut(BaseModel):
    id: int
    patient_id: int
    unit_type: str | None
    admit_time: datetime
    discharge_time: datetime | None

    class Config:
        from_attributes = True


class MeasurementCreate(BaseModel):
    icu_stay_id: int
    measurement_time: datetime
    sepsis_label: int | None = None
    values_json: dict[str, Any]


class AlertActionRequest(BaseModel):
    user_id: int
    notes: str | None = None
    interventions_json: dict[str, Any] | None = None


class AlertOverrideRequest(BaseModel):
    user_id: int
    override_reason: str
    notes: str | None = None


class RiskAssessmentOut(BaseModel):
    id: int
    measurement_id: int
    stage1_score: float
    stage1_level: str
    stage2_score: float | None
    stage2_level: str | None
    explanation_json: dict[str, Any] | None
    predicted_at: datetime

    class Config:
        from_attributes = True
