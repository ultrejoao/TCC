"""Versionamento de modelos de ML.

Toda previsao referencia o modelo que a gerou. Sem isso nao ha como auditar um
diagnostico depois que o modelo for retreinado — requisito de rastreabilidade.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk


class MLModel(Base, TimestampMixin):
    __tablename__ = "ml_models"

    id: Mapped[uuid.UUID] = uuid_pk()
    version: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    algorithm: Mapped[str] = mapped_column(String(80), nullable=False)

    hyperparameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    feature_columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # contexto de treino, para reprodutibilidade
    dataset: Mapped[str | None] = mapped_column(String(255))
    n_windows: Mapped[int | None] = mapped_column(Integer)
    n_features: Mapped[int | None] = mapped_column(Integer)
    window_seconds: Mapped[float | None] = mapped_column()
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))

    # limitacoes conhecidas viajam junto com o modelo, para aparecerem na
    # interface e nao ficarem esquecidas na documentacao
    known_limitations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="ml_model")  # noqa: F821
