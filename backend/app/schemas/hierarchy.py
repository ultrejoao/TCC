"""Schemas da arvore Planta > Area > Linha."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _codigo(v: str) -> str:
    v = v.strip().upper().replace(" ", "-")
    if not v:
        raise ValueError("codigo nao pode ser vazio")
    return v


class PlantCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=160)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    _norm = field_validator("code")(classmethod(lambda cls, v: _codigo(v)))


class AreaCreate(BaseModel):
    plant_id: uuid.UUID
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)

    _norm = field_validator("code")(classmethod(lambda cls, v: _codigo(v)))


class LineCreate(BaseModel):
    area_id: uuid.UUID
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)

    _norm = field_validator("code")(classmethod(lambda cls, v: _codigo(v)))


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    created_at: datetime


class PlantOut(NodeOut):
    location: str | None = None


class AreaOut(NodeOut):
    plant_id: uuid.UUID


class LineOut(NodeOut):
    area_id: uuid.UUID


# --- arvore para navegacao na interface -------------------------------------
class TreeMotor(BaseModel):
    id: uuid.UUID
    tag: str
    name: str
    criticality: str
    last_severity: str | None = None
    open_alerts: int = 0
    max_priority: float = 0.0


class TreeLine(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    motors: list[TreeMotor] = []
    open_alerts: int = 0


class TreeArea(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    lines: list[TreeLine] = []
    open_alerts: int = 0


class TreePlant(BaseModel):
    """Arvore completa da planta, com o resumo de alertas agregado por nivel.

    Os contadores sobem na hierarquia: o alerta de um motor aparece na linha, na
    area e na planta, para que o tecnico enxergue onde esta o problema sem
    precisar abrir cada no.
    """

    id: uuid.UUID
    code: str
    name: str
    location: str | None = None
    areas: list[TreeArea] = []
    open_alerts: int = 0
    motor_count: int = 0
