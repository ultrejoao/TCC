"""Schemas de inspecao de campo.

A inspecao e o unico ponto do sistema em que entra informacao que o modelo nao
produziu: o que o tecnico encontrou ao abrir a maquina. E o que permite medir
acerto contra a realidade, e nao contra a particao de teste.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.measurement import FAULT_TYPES

FaultTypeStr = str


class InspectionCreate(BaseModel):
    motor_id: uuid.UUID
    performed_at: datetime
    prediction_id: uuid.UUID | None = None
    alert_id: uuid.UUID | None = None

    findings: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)

    #: O que a inspecao encontrou de fato. Fica opcional porque nem toda
    #: inspecao conclui um tipo — "nada encontrado" e diferente de "normal
    #: confirmado", e forcar uma escolha produziria rotulo falso.
    confirmed_fault_type: FaultTypeStr | None = None

    def validar_tipo(self) -> None:
        if self.confirmed_fault_type and self.confirmed_fault_type not in FAULT_TYPES:
            raise ValueError(
                f"confirmed_fault_type deve ser um de {FAULT_TYPES}")


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    motor_id: uuid.UUID
    prediction_id: uuid.UUID | None
    alert_id: uuid.UUID | None
    performed_at: datetime
    findings: str | None
    notes: str | None
    confirmed_fault_type: str | None
    created_at: datetime

    # preenchidos quando ha previsao vinculada, para a listagem mostrar o
    # confronto sem exigir uma segunda requisicao
    predicted_fault_type: str | None = None
    predicted_severity: str | None = None
    model_version: str | None = None
    agreement: bool | None = None


class FieldAccuracyByModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    n_confirmed: int
    n_correct: int
    accuracy: float | None


class FieldAccuracy(BaseModel):
    """Acerto medido contra inspecao de campo.

    Difere da acuracia de validacao cruzada em natureza, nao so em valor: aqui
    a verdade vem de alguem que abriu a maquina. Tambem e enviesada por
    construcao — inspeciona-se mais o que o sistema apontou como problema, e
    quase nunca o que ele chamou de saudavel. O campo `caveat` carrega esse
    aviso junto do numero para que ele nao circule sozinho.
    """

    n_inspections: int
    n_confirmed: int
    n_correct: int
    accuracy: float | None
    confusion: dict[str, dict[str, int]]
    by_model: list[FieldAccuracyByModel]
    caveat: str
