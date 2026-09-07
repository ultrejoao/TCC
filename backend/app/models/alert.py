"""Alertas e inspecoes de campo."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

ALERT_STATUS = ("OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED")
ALERT_SEVERITIES = ("WARNING", "FAILURE")


class Alert(Base, TimestampMixin):
    """Gerado a partir de uma previsao.

    Politica: HEALTHY nao gera alerta; WARNING recomenda inspecao; FAILURE
    recomenda intervencao. Divergencia entre modelo e evidencia fisica tambem
    abre alerta, ainda que a severidade prevista seja baixa.
    """

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_motor_status", "motor_id", "status"),
        Index("ix_alerts_status_priority", "status", "priority_score"),
        CheckConstraint(f"status IN {ALERT_STATUS}", name="ck_alerts_status"),
        CheckConstraint(f"severity IN {ALERT_SEVERITIES}", name="ck_alerts_severity"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    motor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("motors.id", ondelete="CASCADE"),
        nullable=False, index=True)
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("predictions.id", ondelete="SET NULL"), index=True)

    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="OPEN", index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # --- por que este alerta existe ----------------------------------------
    # A regra que disparou fica gravada: a pergunta "por que este alerta foi
    # gerado?" precisa ter resposta exata, e nao reconstruida a posteriori.
    rule: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # score de prioridade para a fila de inspecao
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0,
                                                  index=True)

    # snapshot do diagnostico no momento do alerta: o modelo pode ser retreinado
    # e a previsao reavaliada, mas o alerta guarda o que se sabia quando disparou
    fault_type: Mapped[str | None] = mapped_column(String(20))
    physical_type: Mapped[str | None] = mapped_column(String(20))
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_agreement: Mapped[bool | None] = mapped_column(Boolean)
    trend_pct: Mapped[float | None] = mapped_column(Float)
    indicators: Mapped[dict | None] = mapped_column(JSONB)

    # rastreabilidade explicita do modelo, sem depender de navegar pela previsao
    ml_model_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ml_models.id", ondelete="RESTRICT"),
        index=True)

    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_taken: Mapped[str | None] = mapped_column(Text)


class Inspection(Base, TimestampMixin):
    """Inspecao registrada em campo, tipicamente resposta a um alerta."""

    __tablename__ = "inspections"

    id: Mapped[uuid.UUID] = uuid_pk()
    motor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("motors.id", ondelete="CASCADE"),
        nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"))

    # Qual previsao esta inspecao confirma ou refuta. O vinculo e explicito, e
    # nao reconstruido depois pela data: uma inspecao de rotina nao tem alerta,
    # e e justamente ela que mede o acerto em condicao normal — o caso que a
    # validacao cruzada acerta menos (76 %) e que mais aparece em campo.
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("predictions.id", ondelete="SET NULL"),
        index=True)

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True)
    findings: Mapped[str | None] = mapped_column(Text)

    # confirmacao de campo: permite medir na pratica o acerto do modelo
    confirmed_fault_type: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
