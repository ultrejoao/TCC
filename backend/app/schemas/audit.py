"""Schemas da trilha de auditoria.

Somente leitura: nao ha schema de criacao porque a trilha nao aceita escrita
pela API. Os eventos sao gravados pelos proprios fluxos que auditam.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    entity: str | None
    entity_id: uuid.UUID | None
    detail: dict | None
    ip_address: str | None
    created_at: datetime

    user_name: str | None = None

    #: Marca acoes que indicam abuso ou perda de dado, e nao operacao normal.
    #: Fica no servidor para que a interface nao precise conhecer a lista.
    sensitive: bool = False


class AuditSummary(BaseModel):
    days: int
    total: int
    by_action: dict[str, int]
    sensitive: dict[str, int]
    first_event: datetime | None
    last_event: datetime | None
