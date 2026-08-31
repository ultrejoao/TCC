"""Alertas, inspecoes e manutencoes."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True)
    findings: Mapped[str | None] = mapped_column(Text)

    # confirmacao de campo: permite medir na pratica o acerto do modelo
    confirmed_fault_type: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)


class Maintenance(Base, TimestampMixin):
    """Intervencao executada no motor."""

    __tablename__ = "maintenances"

    id: Mapped[uuid.UUID] = uuid_pk()
    motor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("motors.id", ondelete="CASCADE"),
        nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True)
    maintenance_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parts_replaced: Mapped[str | None] = mapped_column(Text)
    downtime_hours: Mapped[float | None] = mapped_column()
