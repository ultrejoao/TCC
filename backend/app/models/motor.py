"""Setores e motores monitorados."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk


class Motor(Base, TimestampMixin):
    """Motor cadastrado.

    Exclusao e SOFT (deleted_at): o historico de medicoes e previsoes precisa
    sobreviver a remocao do motor do cadastro ativo, tanto para auditoria quanto
    para a rastreabilidade exigida pelo versionamento de modelos.
    """

    __tablename__ = "motors"
    __table_args__ = (
        UniqueConstraint("tag", name="uq_motors_tag"),
        CheckConstraint("criticality IN ('A','B','C')", name="ck_motors_criticality"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tag: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    line_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("lines.id", ondelete="SET NULL"), index=True)

    # Criticidade para a producao, cadastrada pela manutencao. Pondera o score
    # de prioridade: uma falha identica pesa mais num motor que para a linha.
    #   A = parada de linha | B = impacto parcial | C = redundante
    criticality: Mapped[str] = mapped_column(String(1), nullable=False, default="B")

    # dados de placa — usados na validacao de faixa e na classe ISO
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    power_kw: Mapped[float | None] = mapped_column(Float)
    rated_rpm: Mapped[int | None] = mapped_column(Integer)
    poles: Mapped[int | None] = mapped_column(Integer)
    rated_current_a: Mapped[float | None] = mapped_column(Float)
    rated_voltage_v: Mapped[float | None] = mapped_column(Float)

    # classe de maquina da ISO 10816-1, define os limiares de zona A/B/C/D
    iso_machine_class: Mapped[str] = mapped_column(String(4), nullable=False, default="I")

    # Baseline OPCIONAL: medicao marcada pelo tecnico como referencia saudavel.
    # Quando ausente, o sistema opera so com o modelo e os indicadores absolutos.
    baseline_measurement_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("measurements.id", ondelete="SET NULL", use_alter=True,
                   name="fk_motors_baseline_measurement"))

    notes: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    line: Mapped["Line | None"] = relationship(  # noqa: F821
        back_populates="motors", foreign_keys=[line_id])
    measurements: Mapped[list["Measurement"]] = relationship(  # noqa: F821
        back_populates="motor", foreign_keys="Measurement.motor_id")
    baseline_measurement: Mapped["Measurement | None"] = relationship(  # noqa: F821
        foreign_keys=[baseline_measurement_id], post_update=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
