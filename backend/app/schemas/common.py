"""Schemas compartilhados: paginacao."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Envelope de listagem paginada.

    A especificacao pede paginacao em todos os endpoints de historico: o volume
    de medicoes por motor cresce sem limite ao longo do tempo, e uma listagem
    sem corte acabaria carregando anos de dados numa unica resposta.
    """

    items: list[T]
    total: int = Field(description="total de registros que atendem ao filtro")
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total
