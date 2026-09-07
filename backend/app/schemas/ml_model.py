"""Schemas de exposicao do registro de modelos.

O que se publica aqui e a ficha do modelo: como foi treinado, quanto acertou,
sob que protocolo, o que ele reconhecidamente nao faz, e quantos diagnosticos
ja saiu dele. E a contrapartida da decisao de que toda previsao referencia o
modelo que a gerou — sem uma superficie de leitura, a rastreabilidade existe no
banco e nao existe para quem opera.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelSummary(BaseModel):
    """Linha da listagem: o suficiente para escolher qual abrir."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    version: str
    algorithm: str
    is_active: bool
    n_features: int | None
    n_windows: int | None
    trained_at: datetime | None
    dataset: str | None

    fault_type_accuracy: float | None
    severity_accuracy: float | None
    protocol: str | None
    prediction_count: int


class ProtocolResult(BaseModel):
    """Desempenho sob um protocolo de validacao.

    Protocolos distintos medem dificuldades distintas de generalizacao, e a
    comparacao entre eles e o resultado metodologico central do trabalho — por
    isso a tela mostra os dois, nunca so o mais favoravel.
    """

    protocol: str
    description: str
    fault_type_accuracy: float | None
    severity_accuracy: float | None
    fault_type_recall: dict[str, float]
    severity_recall: dict[str, float]


class ArtifactIntegrity(BaseModel):
    """Conferencia do artefato em disco contra o hash gravado no registro."""

    path: str
    expected_sha256: str | None
    present: bool
    matches: bool | None
    message: str


class ModelDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    version: str
    algorithm: str
    is_active: bool
    description: str | None
    dataset: str | None
    n_windows: int | None
    n_features: int | None
    window_seconds: float | None
    trained_at: datetime | None

    protocols: list[ProtocolResult]
    known_limitations: list[str]
    hyperparameters: dict
    feature_columns: list[str]
    feature_groups: dict[str, int]

    holdout_note: str | None
    holdout_specimens: list[str]

    integrity: ArtifactIntegrity
    prediction_count: int
    last_prediction_at: datetime | None
