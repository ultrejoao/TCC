"""Arvore de componentes da fabrica: Planta > Area > Linha > Motor.

Niveis fixos, um por tabela. A escolha impoe disciplina no cadastro e torna as
consultas diretas — cada nivel sabe seu pai, e o caminho completo de um motor
sai com dois joins. O custo e que uma fabrica com um nivel a mais exigiria
mudanca de schema; para a planta unica do escopo do TCC, e o compromisso certo.

A exclusao e SOFT em todos os niveis, pelo mesmo motivo dos motores: o historico
de medicoes precisa sobreviver a reorganizacao do cadastro.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk


class Plant(Base, TimestampMixin):
    """Planta industrial — raiz da arvore."""

    __tablename__ = "plants"
    __table_args__ = (UniqueConstraint("code", name="uq_plants_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    areas: Mapped[list["Area"]] = relationship(back_populates="plant")


class Area(Base, TimestampMixin):
    """Area produtiva dentro de uma planta."""

    __tablename__ = "areas"
    __table_args__ = (UniqueConstraint("plant_id", "code", name="uq_areas_plant_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    plant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"),
        nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    plant: Mapped["Plant"] = relationship(back_populates="areas")
    lines: Mapped[list["Line"]] = relationship(back_populates="area")


class Line(Base, TimestampMixin):
    """Linha de producao dentro de uma area. E onde os motores ficam."""

    __tablename__ = "lines"
    __table_args__ = (UniqueConstraint("area_id", "code", name="uq_lines_area_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    area_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("areas.id", ondelete="CASCADE"),
        nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    area: Mapped["Area"] = relationship(back_populates="lines")
    motors: Mapped[list["Motor"]] = relationship(  # noqa: F821
        back_populates="line", foreign_keys="Motor.line_id")
