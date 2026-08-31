"""Schemas de alerta e do painel inicial."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    motor_id: uuid.UUID
    prediction_id: uuid.UUID | None
    ml_model_id: uuid.UUID | None

    severity: str
    status: str
    message: str

    # por que este alerta existe
    rule: str
    reasons: list
    priority_score: float

    # snapshot do diagnostico no momento do disparo
    fault_type: str | None
    physical_type: str | None
    confidence: float | None
    evidence_agreement: bool | None
    trend_pct: float | None
    indicators: dict | None

    acknowledged_at: datetime | None
    resolved_at: datetime | None
    action_taken: str | None
    created_at: datetime


class AlertWithMotor(AlertOut):
    """Alerta com a identificacao do motor e o caminho na hierarquia."""

    motor_tag: str | None = None
    motor_name: str | None = None
    criticality: str | None = None
    line_name: str | None = None
    area_name: str | None = None
    plant_name: str | None = None


class AlertUpdate(BaseModel):
    status: str = Field(pattern="^(ACKNOWLEDGED|RESOLVED|DISMISSED)$")
    action_taken: str | None = Field(default=None, max_length=4000)


class SeverityCounts(BaseModel):
    healthy: int = 0
    warning: int = 0
    failure: int = 0
    unmeasured: int = 0


class CriticalMotor(BaseModel):
    """Linha do ranking de motores que exigem atencao."""

    motor_id: uuid.UUID
    tag: str
    name: str
    criticality: str
    line_name: str | None = None
    area_name: str | None = None

    priority_score: float
    severity: str | None = None
    fault_type: str | None = None
    physical_type: str | None = None
    evidence_agreement: bool | None = None
    confidence: float | None = None
    trend_pct: float | None = None
    open_alerts: int = 0
    top_rule: str | None = None
    reasons: list = []
    last_measurement_at: datetime | None = None


class DashboardOut(BaseModel):
    """Visao inicial: o que precisa de atencao agora, em ordem de prioridade."""

    total_motors: int
    monitored_motors: int
    severity_counts: SeverityCounts

    open_alerts: int
    failure_alerts: int
    divergence_alerts: int = Field(
        description="alertas gerados por divergencia entre modelo e evidencia fisica")

    critical_motors: list[CriticalMotor]
    recent_alerts: list[AlertWithMotor]
    measurements_last_7d: int
