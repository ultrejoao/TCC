"""Inspecoes de campo: o que o tecnico encontrou ao abrir a maquina."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, audit, require_csrf
from app.core.errors import ProblemException
from app.database import get_db
from app.models.alert import Inspection
from app.models.measurement import FAULT_TYPES, Prediction
from app.models.ml_model import MLModel
from app.models.motor import Motor
from app.schemas.inspection import (
    FieldAccuracy,
    FieldAccuracyByModel,
    InspectionCreate,
    InspectionOut,
)

router = APIRouter(prefix="/inspections", tags=["inspecoes"])
DbSession = Annotated[Session, Depends(get_db)]

#: Abaixo disto a acuracia de campo e ruido: uma inspecao a mais move o numero
#: em dezenas de pontos. O endpoint devolve os dados, mas marca a insuficiencia.
MINIMO_INTERPRETAVEL = 20

CAVEAT = (
    "Acerto medido contra inspecao de campo, nao contra particao de teste. "
    "A amostra e enviesada por construcao: inspeciona-se o que o sistema "
    "apontou como problema, e raramente o que ele classificou como saudavel. "
    "Serve para detectar erro sistematico, nao como estimativa de acuracia."
)


def _com_previsao(insp: Inspection, prev: Prediction | None,
                  versao: str | None) -> InspectionOut:
    saida = InspectionOut.model_validate(insp)
    if prev is None:
        return saida
    saida.predicted_fault_type = prev.fault_type
    saida.predicted_severity = prev.severity
    saida.model_version = versao
    if insp.confirmed_fault_type:
        saida.agreement = prev.fault_type == insp.confirmed_fault_type
    return saida


@router.post("", response_model=InspectionOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def registrar_inspecao(dados: InspectionCreate, request: Request, db: DbSession,
                       usuario: CurrentUser) -> InspectionOut:
    """Registra o que a inspecao encontrou."""
    try:
        dados.validar_tipo()
    except ValueError as e:
        raise ProblemException(
            status_code=422, title="Tipo de falha invalido", detail=str(e)) from e

    motor = db.get(Motor, dados.motor_id)
    if motor is None or motor.deleted_at is not None:
        raise ProblemException(
            status_code=404, title="Motor nao encontrado",
            detail="Nao ha motor ativo com este identificador.")

    previsao = None
    if dados.prediction_id:
        previsao = db.get(Prediction, dados.prediction_id)
        if previsao is None:
            raise ProblemException(
                status_code=404, title="Previsao nao encontrada",
                detail="A previsao referenciada nao existe.")
        # Confirmar a previsao de outro motor produziria um acerto sem sentido.
        if previsao.measurement.motor_id != dados.motor_id:
            raise ProblemException(
                status_code=422, title="Previsao de outro motor",
                detail="A previsao referenciada nao pertence a este motor.")

    inspecao = Inspection(
        motor_id=dados.motor_id, user_id=usuario.id,
        alert_id=dados.alert_id, prediction_id=dados.prediction_id,
        performed_at=dados.performed_at, findings=dados.findings,
        notes=dados.notes, confirmed_fault_type=dados.confirmed_fault_type)
    db.add(inspecao)
    db.flush()

    audit(db, request, usuario, "inspection_created", "inspection", inspecao.id,
          motor_id=str(dados.motor_id),
          confirmed_fault_type=dados.confirmed_fault_type)
    db.commit()
    db.refresh(inspecao)

    versao = db.get(MLModel, previsao.ml_model_id).version if previsao else None
    return _com_previsao(inspecao, previsao, versao)


@router.get("", response_model=list[InspectionOut])
def listar_inspecoes(db: DbSession, _: CurrentUser,
                     motor_id: uuid.UUID | None = None,
                     limit: Annotated[int, Query(ge=1, le=200)] = 50
                     ) -> list[InspectionOut]:
    """Inspecoes registradas, da mais recente para a mais antiga."""
    consulta = select(Inspection).order_by(Inspection.performed_at.desc()).limit(limit)
    if motor_id:
        consulta = consulta.where(Inspection.motor_id == motor_id)

    inspecoes = db.scalars(consulta).all()
    versoes = {m.id: m.version for m in db.scalars(select(MLModel)).all()}

    saida = []
    for i in inspecoes:
        prev = db.get(Prediction, i.prediction_id) if i.prediction_id else None
        saida.append(_com_previsao(i, prev, versoes.get(prev.ml_model_id) if prev else None))
    return saida


@router.get("/field-accuracy", response_model=FieldAccuracy)
def acerto_em_campo(db: DbSession, _: CurrentUser) -> FieldAccuracy:
    """Confronta o tipo previsto com o tipo confirmado na inspecao."""
    inspecoes = db.scalars(select(Inspection)).all()

    confirmadas = [i for i in inspecoes
                   if i.confirmed_fault_type and i.prediction_id]

    confusao = {real: {prev: 0 for prev in FAULT_TYPES} for real in FAULT_TYPES}
    por_modelo: dict[uuid.UUID, list[int]] = {}
    acertos = 0

    for i in confirmadas:
        prev = db.get(Prediction, i.prediction_id)
        if prev is None:
            continue
        certo = prev.fault_type == i.confirmed_fault_type
        acertos += certo
        if i.confirmed_fault_type in confusao and prev.fault_type in confusao:
            confusao[i.confirmed_fault_type][prev.fault_type] += 1
        n, c = por_modelo.get(prev.ml_model_id, [0, 0])
        por_modelo[prev.ml_model_id] = [n + 1, c + certo]

    versoes = {m.id: m.version for m in db.scalars(select(MLModel)).all()}
    n = len(confirmadas)

    aviso = CAVEAT
    if n < MINIMO_INTERPRETAVEL:
        aviso = (f"Amostra insuficiente: {n} confirmacao(oes). Abaixo de "
                 f"{MINIMO_INTERPRETAVEL}, uma inspecao a mais desloca o "
                 f"percentual em dezenas de pontos. " + CAVEAT)

    return FieldAccuracy(
        n_inspections=len(inspecoes), n_confirmed=n, n_correct=acertos,
        accuracy=(acertos / n) if n else None,
        confusion=confusao,
        by_model=[
            FieldAccuracyByModel(
                model_version=versoes.get(mid, "?"), n_confirmed=v[0],
                n_correct=v[1], accuracy=(v[1] / v[0]) if v[0] else None)
            for mid, v in sorted(por_modelo.items(), key=lambda kv: -kv[1][0])],
        caveat=aviso)


@router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_csrf)])
def remover_inspecao(inspection_id: uuid.UUID, request: Request, db: DbSession,
                     usuario: CurrentUser) -> Response:
    """Remove uma inspecao registrada por engano.

    Diferente de motores, aqui a remocao e definitiva: um rotulo de campo
    errado contamina a medida de acerto enquanto existir, e manter o registro
    "inativo" so adiaria a decisao de confiar ou nao nele.
    """
    inspecao = db.get(Inspection, inspection_id)
    if inspecao is None:
        raise ProblemException(
            status_code=404, title="Inspecao nao encontrada",
            detail="Nao ha inspecao com este identificador.")

    audit(db, request, usuario, "inspection_deleted", "inspection", inspection_id,
          motor_id=str(inspecao.motor_id),
          confirmed_fault_type=inspecao.confirmed_fault_type)
    db.delete(inspecao)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
