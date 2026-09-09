"""Registro de modelos: qual esta ativo, quanto acerta e o que nao faz.


"""

import hashlib
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import CurrentUser
from app.core.errors import ProblemException
from app.database import get_db
from app.models.measurement import Prediction
from app.models.ml_model import MLModel
from app.schemas.ml_model import (
    ArtifactIntegrity,
    ModelDetail,
    ModelSummary,
    ProtocolResult,
)

router = APIRouter(prefix="/models", tags=["modelos"])
DbSession = Annotated[Session, Depends(get_db)]

#: O que cada protocolo mede. Sem esta explicacao os numeros parecem uma
#: contradicao ("por que o mesmo modelo tem duas acuracias?") em vez do
#: resultado metodologico que sao.
PROTOCOLOS = {
    "leave-one-specimen-out": (
        "Cada montagem fisica de defeito e testada por um modelo que nunca a "
        "viu, em nenhuma carga. E o cenario mais proximo de um motor novo."
    ),
    "leave-one-load-out": (
        "Treina em duas cargas e testa na terceira. O mesmo especime aparece "
        "nos dois lados, entao ha vazamento declarado — serve de limite "
        "superior, nao de estimativa de campo."
    ),
}

#: Rotulos dos grupos de features, pelo prefixo da coluna.
GRUPOS = {
    "vib_": "vibracao",
    "cur_": "corrente",
    "iso_": "indicadores normativos",
}


def _agrupar_features(colunas: list[str]) -> dict[str, int]:
    grupos: dict[str, int] = {}
    for coluna in colunas:
        rotulo = next((v for k, v in GRUPOS.items() if coluna.startswith(k)),
                      "condicao operacional")
        grupos[rotulo] = grupos.get(rotulo, 0) + 1
    return grupos


def _integridade(modelo: MLModel) -> ArtifactIntegrity:
    """Confere o artefato em disco contra o hash gravado no registro.

    Um artefato substituido sem passar pelo registro produz diagnosticos que
    referenciam uma versao que nao e a que rodou. E silencioso por natureza:
    so aparece se alguem comparar os hashes.
    """
    caminho = Path(modelo.artifact_path)
    if not caminho.is_absolute():
        caminho = get_settings().model_artifact.parent.parent.parent / caminho

    if not caminho.exists():
        return ArtifactIntegrity(
            path=modelo.artifact_path, expected_sha256=modelo.artifact_sha256,
            present=False, matches=None,
            message="Artefato ausente no disco: este modelo nao pode ser carregado.")

    if not modelo.artifact_sha256:
        return ArtifactIntegrity(
            path=modelo.artifact_path, expected_sha256=None,
            present=True, matches=None,
            message="Registro sem hash: a integridade nao pode ser verificada.")

    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    confere = h.hexdigest() == modelo.artifact_sha256

    return ArtifactIntegrity(
        path=modelo.artifact_path, expected_sha256=modelo.artifact_sha256,
        present=True, matches=confere,
        message=("Artefato integro: confere com o hash do registro." if confere else
                 "DIVERGENTE: o arquivo em disco nao e o que foi registrado. "
                 "As previsoes desta versao podem nao ser reproduziveis."))


def _protocolos(metrics: dict) -> list[ProtocolResult]:
    """Desdobra o campo `metrics` nos protocolos avaliados.

    O protocolo principal fica na raiz; os demais, em subdicionarios nomeados
    pelo protocolo. Nem todos trazem recall por classe.
    """
    saida: list[ProtocolResult] = []

    principal = metrics.get("protocol")
    if principal:
        saida.append(ProtocolResult(
            protocol=principal,
            description=PROTOCOLOS.get(principal, ""),
            fault_type_accuracy=metrics.get("fault_type_accuracy"),
            severity_accuracy=metrics.get("severity_accuracy"),
            fault_type_recall=metrics.get("fault_type_recall") or {},
            severity_recall=metrics.get("severity_recall") or {}))

    for chave, valor in metrics.items():
        if not isinstance(valor, dict) or chave.endswith("_recall"):
            continue
        nome = chave.replace("_", "-")
        if nome == principal or "accuracy" not in str(valor):
            continue
        saida.append(ProtocolResult(
            protocol=nome,
            description=PROTOCOLOS.get(nome, ""),
            fault_type_accuracy=valor.get("fault_type_accuracy"),
            severity_accuracy=valor.get("severity_accuracy"),
            fault_type_recall=valor.get("fault_type_recall") or {},
            severity_recall=valor.get("severity_recall") or {}))

    return saida


def _contagens(db: Session) -> dict:
    """Quantas previsoes cada modelo gerou, e quando foi a ultima."""
    linhas = db.execute(
        select(Prediction.ml_model_id,
               func.count(Prediction.id),
               func.max(Prediction.created_at))
        .group_by(Prediction.ml_model_id)).all()
    return {mid: (n, ultima) for mid, n, ultima in linhas}


@router.get("", response_model=list[ModelSummary])
def listar_modelos(db: DbSession, _: CurrentUser) -> list[ModelSummary]:
    """Modelos registrados, o ativo primeiro."""
    modelos = db.scalars(
        select(MLModel).order_by(MLModel.is_active.desc(), MLModel.version)).all()
    contagens = _contagens(db)

    return [
        ModelSummary(
            version=m.version, algorithm=m.algorithm, is_active=m.is_active,
            n_features=m.n_features, n_windows=m.n_windows,
            trained_at=m.trained_at, dataset=m.dataset,
            fault_type_accuracy=(m.metrics or {}).get("fault_type_accuracy"),
            severity_accuracy=(m.metrics or {}).get("severity_accuracy"),
            protocol=(m.metrics or {}).get("protocol"),
            prediction_count=contagens.get(m.id, (0, None))[0])
        for m in modelos
    ]


@router.get("/{version}", response_model=ModelDetail)
def detalhar_modelo(version: str, db: DbSession, _: CurrentUser) -> ModelDetail:
    """Ficha completa de uma versao, incluindo o que ela reconhecidamente nao faz."""
    modelo = db.scalar(select(MLModel).where(MLModel.version == version))
    if modelo is None:
        raise ProblemException(
            status_code=404, title="Modelo nao encontrado",
            detail=f"Nenhum modelo registrado com a versao '{version}'.")

    metrics = modelo.metrics or {}
    holdout = metrics.get("holdout") or {}
    n, ultima = _contagens(db).get(modelo.id, (0, None))

    return ModelDetail(
        version=modelo.version, algorithm=modelo.algorithm,
        is_active=modelo.is_active, description=modelo.notes,
        dataset=modelo.dataset, n_windows=modelo.n_windows,
        n_features=modelo.n_features, window_seconds=modelo.window_seconds,
        trained_at=modelo.trained_at,
        protocols=_protocolos(metrics),
        known_limitations=modelo.known_limitations or [],
        hyperparameters=modelo.hyperparameters or {},
        feature_columns=modelo.feature_columns or [],
        feature_groups=_agrupar_features(modelo.feature_columns or []),
        holdout_note=holdout.get("note"),
        holdout_specimens=holdout.get("specimens") or [],
        integrity=_integridade(modelo),
        prediction_count=n, last_prediction_at=ultima)
