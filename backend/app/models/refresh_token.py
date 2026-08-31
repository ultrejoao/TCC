"""Refresh tokens emitidos, com rotacao e deteccao de reuso.

Cada renovacao invalida o token usado e emite outro, encadeado por
`replaced_by_jti`. Se um token JA USADO reaparece, a interpretacao e que ele
vazou: nesse caso toda a familia de tokens daquele usuario e revogada, forcando
novo login. E a recomendacao da OWASP para refresh token rotation.

Guarda-se apenas o `jti` (identificador do token), nunca o token em si.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, uuid_pk


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True)

    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(40))
    replaced_by_jti: Mapped[str | None] = mapped_column(String(36))

    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship()  # noqa: F821

    def is_usable(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now
