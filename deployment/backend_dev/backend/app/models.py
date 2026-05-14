from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    alerts = relationship("Alert", back_populates="acted_by_user")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_patient_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    icu_stays = relationship("ICUStay", back_populates="patient")


class ICUStay(Base):
    __tablename__ = "icu_stays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    unit_type: Mapped[str] = mapped_column(String(64), nullable=True)
    admit_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discharge_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    patient = relationship("Patient", back_populates="icu_stays")
    measurements = relationship("HourlyMeasurement", back_populates="icu_stay")


class HourlyMeasurement(Base):
    __tablename__ = "hourly_measurements"
    __table_args__ = (UniqueConstraint("icu_stay_id", "measurement_time", name="uq_stay_measurement_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    icu_stay_id: Mapped[int] = mapped_column(ForeignKey("icu_stays.id"), nullable=False, index=True)
    measurement_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    sepsis_label: Mapped[int] = mapped_column(Integer, nullable=True)
    values_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    icu_stay = relationship("ICUStay", back_populates="measurements")
    risk_assessments = relationship("RiskAssessment", back_populates="measurement")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    measurement_id: Mapped[int] = mapped_column(ForeignKey("hourly_measurements.id"), nullable=False, index=True)
    stage1_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    stage1_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stage2_score: Mapped[float] = mapped_column(Float, nullable=True, index=True)
    stage2_level: Mapped[str] = mapped_column(String(16), nullable=True, index=True)
    explanation_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    measurement = relationship("HourlyMeasurement", back_populates="risk_assessments")
    alerts = relationship("Alert", back_populates="risk_assessment")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    risk_assessment_id: Mapped[int] = mapped_column(ForeignKey("risk_assessments.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    acted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    acted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=True)
    override_reason: Mapped[str] = mapped_column(String(128), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    interventions_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    requires_acknowledgment: Mapped[bool] = mapped_column(Boolean, default=True)

    risk_assessment = relationship("RiskAssessment", back_populates="alerts")
    acted_by_user = relationship("User", back_populates="alerts")
