"""Schemas de medicao e previsao."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Faixas plausiveis para validacao de range dos valores enviados pelo tecnico.
# Rejeitar o implausivel na entrada evita gravar dado impossivel e evita que o
# modelo receba entrada fora do dominio em que foi treinado.
RANGES = {
    "load_nm": (0.0, 10_000.0),
    "rpm": (0.0, 60_000.0),
    "temperature_c": (-50.0, 300.0),
    "voltage_v": (0.0, 50_000.0),
    "current_a": (0.0, 10_000.0),
    "sample_rate_hz": (100.0, 200_000.0),
}


class MeasurementContext(BaseModel):
    """Dados que acompanham o arquivo de sinal no formulario de campo."""

    motor_id: uuid.UUID
    collected_at: datetime | None = Field(
        default=None, description="quando a coleta foi feita; padrao: agora")

    load_nm: float | None = Field(default=None, ge=RANGES["load_nm"][0],
                                  le=RANGES["load_nm"][1])
    rpm: float | None = Field(default=None, ge=RANGES["rpm"][0], le=RANGES["rpm"][1])

    # variaveis operacionais complementares: registradas, FORA do modelo v1
    temperature_c: float | None = Field(default=None, ge=RANGES["temperature_c"][0],
                                        le=RANGES["temperature_c"][1])
    voltage_v: float | None = Field(default=None, ge=RANGES["voltage_v"][0],
                                    le=RANGES["voltage_v"][1])
    current_a: float | None = Field(default=None, ge=RANGES["current_a"][0],
                                    le=RANGES["current_a"][1])
    operating_hours: float | None = Field(default=None, ge=0, le=1_000_000)

    # necessarios quando o formato do arquivo nao os informa (CSV, NPY)
    sample_rate_hz: float | None = Field(default=None, ge=RANGES["sample_rate_hz"][0],
                                         le=RANGES["sample_rate_hz"][1])
    unit: str | None = Field(default=None, pattern="^(m/s\\^2|m/s2|g|mm/s\\^2)$")
    channel: int = Field(default=0, ge=0, le=15,
                         description="canal a analisar no perfil de canal unico")

    is_baseline: bool = Field(
        default=False,
        description="marcar como medicao de referencia do motor (condicao normal)")
    notes: str | None = Field(default=None, max_length=4000)


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    # severidade por criterio fisico (saida primaria)
    severity: str
    severity_criterion: str | None
    severity_explanation: str | None
    ratio_to_baseline: float | None

    # severidade prevista pelo modelo (experimento preliminar, informativa)
    ml_severity: str | None
    severity_probabilities: dict

    fault_type: str
    fault_type_probabilities: dict
    physical_type: str | None
    evidence_agreement: bool
    confidence: float
    recommendation: str
    top_factors: list
    baseline_comparison: dict | None
    inference_ms: float | None
    created_at: datetime


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    motor_id: uuid.UUID
    collected_at: datetime
    load_nm: float | None
    rpm: float | None
    temperature_c: float | None
    is_baseline: bool

    source_filename: str | None
    sample_rate_hz: float
    n_samples: int
    n_channels: int
    duration_s: float

    iso_v_rms_mms: float | None
    iso_v_1x_mms: float | None
    iso_v_2x_mms: float | None
    iso_a_hf_g: float | None
    iso_zone: str | None

    notes: str | None
    created_at: datetime


class MeasurementWithPrediction(MeasurementOut):
    """Resposta do POST /measurements: medicao gravada e diagnostico, juntos."""

    prediction: PredictionOut | None = None
    model_version: str | None = None
    profile: str | None = None
    profile_note: str | None = None
    alert_id: uuid.UUID | None = None
