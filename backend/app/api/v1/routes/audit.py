"""Leitura da trilha de auditoria"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.database import get_db
from app.models.user import AuditLog, User
from app.schemas.audit import AuditEntry, AuditSummary
from app.schemas.common import Page

router = APIRouter(prefix="/audit", tags=["auditoria"])
DbSession = Annotated[Session, Depends(get_db)]

#: Acoes que merecem destaque na leitura: indicam tentativa de abuso ou perda
#: de dado, e nao operacao normal.
ACOES_SENSIVEIS = frozenset({
    "refresh_reuse_detected", "login_failed", "motor_deleted",
    "inspection_deleted", "csrf_rejected",
})


@router.get("", response_model=Page[AuditEntry])
def listar(db: DbSession, _: CurrentUser,
           action: str | None = None,
           entity_id: uuid.UUID | None = None,
           only_sensitive: bool = False,
           limit: Annotated[int, Query(ge=1, le=200)] = 50,
           offset: Annotated[int, Query(ge=0)] = 0) -> Page[AuditEntry]:
    """Eventos registrados, do mais recente para o mais antigo."""
    consulta = select(AuditLog)
    if action:
        consulta = consulta.where(AuditLog.action == action)
    if entity_id:
        consulta = consulta.where(AuditLog.entity_id == entity_id)
    if only_sensitive:
        consulta = consulta.where(AuditLog.action.in_(ACOES_SENSIVEIS))

    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    itens = db.scalars(
        consulta.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all()

    nomes = {u.id: u.name for u in db.scalars(select(User)).all()}

    return Page(
        items=[AuditEntry(
            id=e.id, action=e.action, entity=e.entity, entity_id=e.entity_id,
            detail=e.detail, ip_address=e.ip_address, created_at=e.created_at,
            user_name=nomes.get(e.user_id) if e.user_id else None,
            sensitive=e.action in ACOES_SENSIVEIS) for e in itens],
        total=total, limit=limit, offset=offset)


@router.get("/summary", response_model=AuditSummary)
def resumo(db: DbSession, _: CurrentUser,
           days: Annotated[int, Query(ge=1, le=365)] = 30) -> AuditSummary:
    """Contagem por acao no periodo, com as sensiveis separadas."""
    desde = datetime.now(timezone.utc) - timedelta(days=days)

    linhas = db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .where(AuditLog.created_at >= desde)
        .group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc())).all()

    por_acao = {acao: n for acao, n in linhas}
    return AuditSummary(
        days=days,
        total=sum(por_acao.values()),
        by_action=por_acao,
        sensitive={a: n for a, n in por_acao.items() if a in ACOES_SENSIVEIS},
        first_event=db.scalar(select(func.min(AuditLog.created_at))),
        last_event=db.scalar(select(func.max(AuditLog.created_at))))
