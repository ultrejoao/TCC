"""Medicoes e previsoes.

Fluxo: o tecnico envia o sinal bruto coletado em campo; a API extrai as
features, o modelo classifica e a previsao e gravada junto — tudo na mesma
requisicao.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk

SEVERITIES = ("HEALTHY", "WARNING", "FAILURE")
FAULT_TYPES = ("normal", "bearing", "misalignment", "unbalance")


class Measurement(Base, TimestampMixin):
    __tablename__ = "measurements"
    __table_args__ = (
        # historico por motor e a consulta mais frequente do dashboard
        Index("ix_measurements_motor_created", "motor_id", "created_at"),
        CheckConstraint("sample_rate_hz > 0", name="ck_measurements_sample_rate"),
        CheckConstraint("n_channels > 0", name="ck_measurements_channels"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    motor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("motors.id", ondelete="CASCADE"),
        nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True)

    # condicao de operacao no momento da coleta
    load_nm: Mapped[float | None] = mapped_column(Float)
    rpm: Mapped[float | None] = mapped_column(Float)

    # variaveis operacionais complementares: registradas, FORA do modelo v1
    # (temperatura e impressao digital da sessao; tensao nao existe no dataset)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    voltage_v: Mapped[float | None] = mapped_column(Float)
    current_a: Mapped[float | None] = mapped_column(Float)
    operating_hours: Mapped[float | None] = mapped_column(Float)

    # marcada pelo tecnico como referencia de condicao saudavel (opcional)
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # origem do sinal bruto
    source_filename: Mapped[str | None] = mapped_column(String(255))
    source_path: Mapped[str | None] = mapped_column(String(500))
    source_sha256: Mapped[str | None] = mapped_column(String(64), index=True)

    # Unidade em que o sinal foi declarado no envio. Sem ela o arquivo guardado
    # nao pode ser reinterpretado depois: os mesmos numeros valem 1 ou 9,80665
    # conforme tenham sido enviados em g ou em m/s^2.
    source_unit: Mapped[str | None] = mapped_column(String(10))
    sample_rate_hz: Mapped[float] = mapped_column(Float, nullable=False)
    n_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    n_channels: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, nullable=False)

    # features extraidas do sinal, entrada do modelo
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # indicadores normativos ISO 10816/20816, em colunas para consulta e grafico
    iso_v_rms_mms: Mapped[float | None] = mapped_column(Float)
    iso_v_1x_mms: Mapped[float | None] = mapped_column(Float)
    iso_v_2x_mms: Mapped[float | None] = mapped_column(Float)
    iso_a_hf_g: Mapped[float | None] = mapped_column(Float)
    iso_zone: Mapped[str | None] = mapped_column(String(1))

    notes: Mapped[str | None] = mapped_column(Text)

    motor: Mapped["Motor"] = relationship(  # noqa: F821
        back_populates="measurements", foreign_keys=[motor_id])
    user: Mapped["User | None"] = relationship(back_populates="measurements")  # noqa: F821
    prediction: Mapped["Prediction | None"] = relationship(
        back_populates="measurement", uselist=False, cascade="all, delete-orphan")


class Prediction(Base, TimestampMixin):
    """Resultado do diagnostico de uma medicao.

    Guarda os dois alvos do modelo, o resultado da matriz de decisao e o
    identificador do modelo que gerou a previsao (rastreabilidade obrigatoria).
    """

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(f"severity IN {SEVERITIES}", name="ck_predictions_severity"),
        CheckConstraint(f"fault_type IN {FAULT_TYPES}", name="ck_predictions_fault_type"),
        CheckConstraint("confidence >= 0 AND confidence <= 1",
                        name="ck_predictions_confidence"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    measurement_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("measurements.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True)
    ml_model_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ml_models.id", ondelete="RESTRICT"),
        nullable=False, index=True)

    # SEVERIDADE: vem da avaliacao fisica (ISO 10816), nao do modelo. Ver
    # ml/kaist/physical_severity.py para a justificativa metodologica.
    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    severity_criterion: Mapped[str | None] = mapped_column(String(30))
    severity_explanation: Mapped[str | None] = mapped_column(Text)
    ratio_to_baseline: Mapped[float | None] = mapped_column(Float)

    # Severidade prevista pelo MODELO: resultado do experimento preliminar,
    # guardado para comparacao. Nao alimenta alertas nem decisao.
    ml_severity: Mapped[str | None] = mapped_column(String(10))
    severity_probabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    fault_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fault_type_probabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # matriz de decisao: cruzamento com a evidencia fisica
    physical_type: Mapped[str | None] = mapped_column(String(20))
    evidence_agreement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    # explicabilidade (SHAP) e comparacao com a referencia do motor
    top_factors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    baseline_comparison: Mapped[dict | None] = mapped_column(JSONB)

    inference_ms: Mapped[float | None] = mapped_column(Float)

    measurement: Mapped["Measurement"] = relationship(back_populates="prediction")
    ml_model: Mapped["MLModel"] = relationship(back_populates="predictions")  # noqa: F821
