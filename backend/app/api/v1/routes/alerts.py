"""Alertas e painel inicial.

O painel responde uma pergunta so: **o que precisa de atencao agora?** 
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.alert_policy import AlertRule
from app.core.deps import CurrentUser, audit, require_csrf
from app.core.errors import ProblemException
from app.database import get_db
from app.models.alert import Alert
from app.models.measurement import Measurement, Prediction
from app.models.motor import Motor
from app.schemas.alert import (
    AlertOut,
    AlertUpdate,
    AlertWithMotor,
    CriticalMotor,
    DashboardOut,
    SeverityCounts,
)
from app.schemas.common import Page

router = APIRouter(tags=["alertas"])
DbSession = Annotated[Session, Depends(get_db)]

# Regras cuja origem e a divergencia entre modelo e evidencia fisica.
REGRAS_DIVERGENCIA = (str(AlertRule.DIVERGENCIA_EM_SAUDAVEL),
                      str(AlertRule.DEGRADACAO_INCERTA),
                      str(AlertRule.FALHA_INCERTA))


def _com_motor(alerta: Alert, motor: Motor | None) -> AlertWithMotor:
    saida = AlertWithMotor.model_validate(alerta)
    if motor is None:
        return saida
    saida.motor_tag = motor.tag
    saida.motor_name = motor.name
    saida.criticality = motor.criticality
    if motor.line:
        saida.line_name = motor.line.name
        if motor.line.area:
            saida.area_name = motor.line.area.name
            if motor.line.area.plant:
                saida.plant_name = motor.line.area.plant.name
    return saida


@router.get("/alerts", response_model=Page[AlertWithMotor])
def listar_alertas(
    db: DbSession, user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[str | None, Query(
        alias="status", pattern="^(OPEN|ACKNOWLEDGED|RESOLVED|DISMISSED)$")] = None,
    severity: Annotated[str | None, Query(pattern="^(WARNING|FAILURE)$")] = None,
    motor_id: uuid.UUID | None = None,
    rule: str | None = None,
    only_divergence: bool = False,
    include_deleted_motors: bool = False,
) -> Page[AlertWithMotor]:
    """Alertas ordenados por prioridade, do mais urgente para o menos."""
    condicoes = []
    if not include_deleted_motors:
        condicoes.append(Alert.motor_id.in_(
            select(Motor.id).where(Motor.deleted_at.is_(None))))
    if status_filter:
        condicoes.append(Alert.status == status_filter)
    if severity:
        condicoes.append(Alert.severity == severity)
    if motor_id:
        condicoes.append(Alert.motor_id == motor_id)
    if rule:
        condicoes.append(Alert.rule == rule)
    if only_divergence:
        condicoes.append(Alert.rule.in_(REGRAS_DIVERGENCIA))

    total = db.scalar(select(func.count()).select_from(Alert).where(*condicoes)) or 0
    alertas = list(db.scalars(
        select(Alert).where(*condicoes)
        .order_by(Alert.priority_score.desc(), Alert.created_at.desc())
        .limit(limit).offset(offset)))

    itens = [_com_motor(a, db.get(Motor, a.motor_id)) for a in alertas]
    return Page(items=itens, total=total, limit=limit, offset=offset)


@router.get("/alerts/{alert_id}", response_model=AlertWithMotor)
def obter_alerta(alert_id: uuid.UUID, db: DbSession,
                 user: CurrentUser) -> AlertWithMotor:
    alerta = db.get(Alert, alert_id)
    if alerta is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, "Recurso nao encontrado",
                               "Alerta nao encontrado.")
    return _com_motor(alerta, db.get(Motor, alerta.motor_id))


@router.put("/alerts/{alert_id}", response_model=AlertOut,
            dependencies=[Depends(require_csrf)])
def atualizar_alerta(alert_id: uuid.UUID, payload: AlertUpdate, request: Request,
                     db: DbSession, user: CurrentUser) -> Alert:
    """Reconhece, resolve ou descarta um alerta.

    A acao tomada fica registrada: e ela que permite, depois, confrontar o
    diagnostico do sistema com o que a inspecao encontrou de fato.
    """
    alerta = db.get(Alert, alert_id)
    if alerta is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, "Recurso nao encontrado",
                               "Alerta nao encontrado.")
    if alerta.status in ("RESOLVED", "DISMISSED"):
        raise ProblemException(
            status.HTTP_409_CONFLICT, "Conflito",
            f"Alerta ja esta em '{alerta.status}' e nao pode ser reaberto.")

    agora = datetime.now(timezone.utc)
    alerta.status = payload.status
    if payload.action_taken:
        alerta.action_taken = payload.action_taken
    if payload.status == "ACKNOWLEDGED":
        alerta.acknowledged_by_id = user.id
        alerta.acknowledged_at = agora
    elif payload.status in ("RESOLVED", "DISMISSED"):
        alerta.resolved_at = agora
        if alerta.acknowledged_at is None:
            alerta.acknowledged_by_id = user.id
            alerta.acknowledged_at = agora

    audit(db, request, user, f"alert_{payload.status.lower()}", "alerts", alerta.id,
          rule=alerta.rule, motor_id=str(alerta.motor_id))
    db.commit()
    db.refresh(alerta)
    return alerta


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: DbSession, user: CurrentUser,
              top: Annotated[int, Query(ge=1, le=50)] = 10) -> DashboardOut:
    motores = list(db.scalars(select(Motor).where(Motor.deleted_at.is_(None))))
    ids = [m.id for m in motores]

    contagem = SeverityCounts()
    ultima_por_motor: dict[uuid.UUID, tuple[Prediction, Measurement]] = {}

    if ids:
        for medicao, predicao in db.execute(
                select(Measurement, Prediction)
                .join(Prediction, Prediction.measurement_id == Measurement.id)
                .where(Measurement.motor_id.in_(ids))
                .order_by(Measurement.motor_id, Measurement.created_at.desc())):
            ultima_por_motor.setdefault(medicao.motor_id, (predicao, medicao))

    for motor in motores:
        par = ultima_por_motor.get(motor.id)
        if par is None:
            contagem.unmeasured += 1
        elif par[0].severity == "FAILURE":
            contagem.failure += 1
        elif par[0].severity == "WARNING":
            contagem.warning += 1
        else:
            contagem.healthy += 1

    # apenas alertas de motores ATIVOS: alertas de motor removido do cadastro
    # continuam no historico, mas nao pesam no painel operacional
    abertos = list(db.scalars(
        select(Alert).join(Motor, Motor.id == Alert.motor_id)
        .where(Alert.status == "OPEN", Motor.deleted_at.is_(None))
        .order_by(Alert.priority_score.desc(), Alert.created_at.desc())))

    # --- fila de prioridade: um item por motor, o alerta mais grave dele -----
    criticos: list[CriticalMotor] = []
    vistos: set[uuid.UUID] = set()
    por_motor: dict[uuid.UUID, int] = {}
    for alerta in abertos:
        por_motor[alerta.motor_id] = por_motor.get(alerta.motor_id, 0) + 1

    for alerta in abertos:
        if alerta.motor_id in vistos or len(criticos) >= top:
            continue
        motor = db.get(Motor, alerta.motor_id)
        if motor is None or motor.deleted_at is not None:
            continue
        vistos.add(motor.id)

        par = ultima_por_motor.get(motor.id)
        criticos.append(CriticalMotor(
            motor_id=motor.id, tag=motor.tag, name=motor.name,
            criticality=motor.criticality,
            line_name=motor.line.name if motor.line else None,
            area_name=(motor.line.area.name
                       if motor.line and motor.line.area else None),
            priority_score=alerta.priority_score,
            severity=alerta.severity, fault_type=alerta.fault_type,
            physical_type=alerta.physical_type,
            evidence_agreement=alerta.evidence_agreement,
            confidence=alerta.confidence, trend_pct=alerta.trend_pct,
            open_alerts=por_motor.get(motor.id, 0),
            top_rule=alerta.rule, reasons=alerta.reasons or [],
            last_measurement_at=par[1].collected_at if par else None))

    sete_dias = datetime.now(timezone.utc) - timedelta(days=7)
    recentes = [_com_motor(a, db.get(Motor, a.motor_id)) for a in abertos[:10]]

    return DashboardOut(
        total_motors=len(motores),
        monitored_motors=len(ultima_por_motor),
        severity_counts=contagem,
        open_alerts=len(abertos),
        failure_alerts=sum(1 for a in abertos if a.severity == "FAILURE"),
        divergence_alerts=sum(1 for a in abertos if a.rule in REGRAS_DIVERGENCIA),
        critical_motors=criticos,
        recent_alerts=recentes,
        measurements_last_7d=db.scalar(
            select(func.count()).select_from(Measurement)
            .where(Measurement.created_at >= sete_dias)) or 0,
    )
