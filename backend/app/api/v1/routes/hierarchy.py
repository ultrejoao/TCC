"""Arvore de componentes da fabrica: Planta > Area > Linha.

Alem do CRUD, expoe a arvore completa com os contadores de alerta agregados por
nivel
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, audit, require_csrf
from app.core.errors import ProblemException
from app.database import get_db
from app.models.alert import Alert
from app.models.hierarchy import Area, Line, Plant
from app.models.measurement import Measurement, Prediction
from app.models.motor import Motor
from app.schemas.hierarchy import (
    AreaCreate,
    AreaOut,
    LineCreate,
    LineOut,
    PlantCreate,
    PlantOut,
    TreeArea,
    TreeLine,
    TreeMotor,
    TreePlant,
)

router = APIRouter(tags=["hierarquia"])
DbSession = Annotated[Session, Depends(get_db)]


def _ativo(db: Session, modelo, id_: uuid.UUID, rotulo: str):
    obj = db.get(modelo, id_)
    if obj is None or obj.deleted_at is not None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, "Recurso nao encontrado",
                               f"{rotulo} nao encontrado(a).")
    return obj


# ------------------------------------------------------------------ plantas ---
@router.get("/plants", response_model=list[PlantOut])
def listar_plantas(db: DbSession, user: CurrentUser) -> list[Plant]:
    return list(db.scalars(
        select(Plant).where(Plant.deleted_at.is_(None)).order_by(Plant.code)))


@router.post("/plants", response_model=PlantOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def criar_planta(payload: PlantCreate, request: Request, db: DbSession,
                 user: CurrentUser) -> Plant:
    if db.scalar(select(Plant).where(Plant.code == payload.code)):
        raise ProblemException(status.HTTP_409_CONFLICT, "Conflito",
                               f"Ja existe planta com o codigo '{payload.code}'.")
    planta = Plant(**payload.model_dump())
    db.add(planta)
    db.flush()
    audit(db, request, user, "plant_created", "plants", planta.id, code=planta.code)
    db.commit()
    db.refresh(planta)
    return planta


# -------------------------------------------------------------------- areas ---
@router.get("/areas", response_model=list[AreaOut])
def listar_areas(db: DbSession, user: CurrentUser,
                 plant_id: uuid.UUID | None = None) -> list[Area]:
    condicoes = [Area.deleted_at.is_(None)]
    if plant_id:
        condicoes.append(Area.plant_id == plant_id)
    return list(db.scalars(select(Area).where(*condicoes).order_by(Area.code)))


@router.post("/areas", response_model=AreaOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def criar_area(payload: AreaCreate, request: Request, db: DbSession,
               user: CurrentUser) -> Area:
    _ativo(db, Plant, payload.plant_id, "Planta")
    duplicada = db.scalar(select(Area).where(Area.plant_id == payload.plant_id,
                                             Area.code == payload.code))
    if duplicada:
        raise ProblemException(
            status.HTTP_409_CONFLICT, "Conflito",
            f"Ja existe area '{payload.code}' nesta planta.")
    area = Area(**payload.model_dump())
    db.add(area)
    db.flush()
    audit(db, request, user, "area_created", "areas", area.id, code=area.code)
    db.commit()
    db.refresh(area)
    return area


# ------------------------------------------------------------------- linhas ---
@router.get("/lines", response_model=list[LineOut])
def listar_linhas(db: DbSession, user: CurrentUser,
                  area_id: uuid.UUID | None = None) -> list[Line]:
    condicoes = [Line.deleted_at.is_(None)]
    if area_id:
        condicoes.append(Line.area_id == area_id)
    return list(db.scalars(select(Line).where(*condicoes).order_by(Line.code)))


@router.post("/lines", response_model=LineOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def criar_linha(payload: LineCreate, request: Request, db: DbSession,
                user: CurrentUser) -> Line:
    _ativo(db, Area, payload.area_id, "Area")
    duplicada = db.scalar(select(Line).where(Line.area_id == payload.area_id,
                                             Line.code == payload.code))
    if duplicada:
        raise ProblemException(
            status.HTTP_409_CONFLICT, "Conflito",
            f"Ja existe linha '{payload.code}' nesta area.")
    linha = Line(**payload.model_dump())
    db.add(linha)
    db.flush()
    audit(db, request, user, "line_created", "lines", linha.id, code=linha.code)
    db.commit()
    db.refresh(linha)
    return linha


# ------------------------------------------------------------------- arvore ---
@router.get("/tree", response_model=list[TreePlant])
def arvore(db: DbSession, user: CurrentUser) -> list[TreePlant]:
    """Arvore completa com alertas agregados de baixo para cima."""
    # alertas abertos e prioridade maxima por motor, em uma consulta
    resumo = {
        row.motor_id: (row.abertos, float(row.prioridade or 0.0))
        for row in db.execute(
            select(Alert.motor_id,
                   func.count().label("abertos"),
                   func.max(Alert.priority_score).label("prioridade"))
            .where(Alert.status == "OPEN")
            .group_by(Alert.motor_id))
    }

    # ultima severidade conhecida de cada motor
    ultima_sev: dict[uuid.UUID, str] = {}
    for motor_id, severidade in db.execute(
            select(Measurement.motor_id, Prediction.severity)
            .join(Prediction, Prediction.measurement_id == Measurement.id)
            .order_by(Measurement.motor_id, Measurement.created_at.desc())):
        ultima_sev.setdefault(motor_id, severidade)

    saida: list[TreePlant] = []
    for planta in db.scalars(select(Plant).where(Plant.deleted_at.is_(None))
                             .order_by(Plant.code)):
        no_planta = TreePlant(id=planta.id, code=planta.code, name=planta.name,
                              location=planta.location, areas=[])

        for area in db.scalars(select(Area).where(Area.plant_id == planta.id,
                                                  Area.deleted_at.is_(None))
                               .order_by(Area.code)):
            no_area = TreeArea(id=area.id, code=area.code, name=area.name, lines=[])

            for linha in db.scalars(select(Line).where(Line.area_id == area.id,
                                                       Line.deleted_at.is_(None))
                                    .order_by(Line.code)):
                no_linha = TreeLine(id=linha.id, code=linha.code, name=linha.name,
                                    motors=[])

                for motor in db.scalars(select(Motor).where(
                        Motor.line_id == linha.id, Motor.deleted_at.is_(None))
                        .order_by(Motor.tag)):
                    abertos, prioridade = resumo.get(motor.id, (0, 0.0))
                    no_linha.motors.append(TreeMotor(
                        id=motor.id, tag=motor.tag, name=motor.name,
                        criticality=motor.criticality,
                        last_severity=ultima_sev.get(motor.id),
                        open_alerts=abertos, max_priority=prioridade))
                    no_linha.open_alerts += abertos

                no_area.lines.append(no_linha)
                no_area.open_alerts += no_linha.open_alerts

            no_planta.areas.append(no_area)
            no_planta.open_alerts += no_area.open_alerts

        no_planta.motor_count = sum(
            len(ln.motors) for ar in no_planta.areas for ln in ar.lines)
        saida.append(no_planta)

    return saida
