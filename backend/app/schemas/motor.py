"""Schemas de setor e motor."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SectorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class SectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class MotorBase(BaseModel):
    tag: str = Field(min_length=1, max_length=60,
                     description="identificacao do motor na planta, ex. MT-101")
    name: str = Field(min_length=2, max_length=160)
    sector_id: uuid.UUID | None = None

    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)

    # Faixas de placa plausiveis para motores industriais. Servem tambem de base
    # para a validacao de range das medicoes.
    power_kw: float | None = Field(default=None, gt=0, le=10_000)
    rated_rpm: int | None = Field(default=None, gt=0, le=60_000)
    poles: int | None = Field(default=None, ge=2, le=48)
    rated_current_a: float | None = Field(default=None, gt=0, le=10_000)
    rated_voltage_v: float | None = Field(default=None, gt=0, le=50_000)

    iso_machine_class: str = Field(default="I", pattern="^(I|II|III|IV)$",
                                   description="classe de maquina da ISO 10816-1")
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("tag")
    @classmethod
    def _tag_limpa(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("tag nao pode ser vazia")
        return v

    @field_validator("poles")
    @classmethod
    def _polos_pares(cls, v: int | None) -> int | None:
        if v is not None and v % 2 != 0:
            raise ValueError("numero de polos deve ser par")
        return v


class MotorCreate(MotorBase):
    pass


class MotorUpdate(BaseModel):
    """Atualizacao parcial: apenas os campos enviados sao alterados."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    sector_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    power_kw: float | None = Field(default=None, gt=0, le=10_000)
    rated_rpm: int | None = Field(default=None, gt=0, le=60_000)
    poles: int | None = Field(default=None, ge=2, le=48)
    rated_current_a: float | None = Field(default=None, gt=0, le=10_000)
    rated_voltage_v: float | None = Field(default=None, gt=0, le=50_000)
    iso_machine_class: str | None = Field(default=None, pattern="^(I|II|III|IV)$")
    notes: str | None = Field(default=None, max_length=4000)
    baseline_measurement_id: uuid.UUID | None = None


class MotorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tag: str
    name: str
    sector_id: uuid.UUID | None
    manufacturer: str | None
    model: str | None
    power_kw: float | None
    rated_rpm: int | None
    poles: int | None
    rated_current_a: float | None
    rated_voltage_v: float | None
    iso_machine_class: str
    baseline_measurement_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class MotorDetail(MotorOut):
    """Motor com o resumo de condicao usado no dashboard."""

    sector_name: str | None = None
    measurement_count: int = 0
    last_measurement_at: datetime | None = None
    last_severity: str | None = None
    last_fault_type: str | None = None
    open_alerts: int = 0
    has_baseline: bool = False
