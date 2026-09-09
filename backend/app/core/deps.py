"""Dependencias de autenticacao e autorizacao do FastAPI."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ProblemException
from app.core.security import csrf_tokens_match, decode_token
from app.database import get_db
from app.models.user import AuditLog, User

settings = get_settings()

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

# Metodos que alteram estado exigem CSRF; leitura nao.
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _nao_autenticado(detalhe: str) -> ProblemException:
    return ProblemException(status.HTTP_401_UNAUTHORIZED, "Nao autenticado", detalhe)


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Usuario autenticado.

    Aceita o token via cookie httpOnly (navegador) ou via cabecalho
    Authorization: Bearer (clientes nao-navegador).
    """
    token = access_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    if not token:
        raise _nao_autenticado("Credenciais ausentes.")

    try:
        payload = decode_token(token, "access")
    except jwt.ExpiredSignatureError:
        raise _nao_autenticado("Sessao expirada. Renove o token.") from None
    except jwt.InvalidTokenError:
        raise _nao_autenticado("Token invalido.") from None

    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise _nao_autenticado("Usuario inexistente ou inativo.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_csrf(
    request: Request,
    csrf_token: Annotated[str | None, Cookie(alias=CSRF_COOKIE)] = None,
    x_csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    """Double-submit token nos metodos que alteram estado.
    """
    if request.method not in UNSAFE_METHODS:
        return
    if request.headers.get("authorization", "").lower().startswith("bearer "):
        return
    if not csrf_tokens_match(csrf_token, x_csrf_token):
        raise ProblemException(
            status.HTTP_403_FORBIDDEN, "Falha na verificacao CSRF",
            f"O cabecalho {CSRF_HEADER} deve repetir o valor do cookie {CSRF_COOKIE}.")


def require_roles(*roles: str):
    """Autorizacao por papel.

    O MVP opera com perfil unico autenticado; a dependencia ja existe para que o
    RBAC completo
    """
    def _check(user: CurrentUser) -> User:
        if roles and user.role not in roles:
            raise ProblemException(
                status.HTTP_403_FORBIDDEN, "Acesso negado",
                f"Esta operacao exige um dos perfis: {', '.join(roles)}.")
        return user
    return _check


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def audit(db: Session, request: Request, user: User | None, action: str,
          entity: str | None = None, entity_id: uuid.UUID | None = None,
          **detail) -> None:
    """Registra uma acao sensivel na trilha de auditoria."""
    db.add(AuditLog(
        user_id=user.id if user else None,
        action=action, entity=entity, entity_id=entity_id,
        detail=detail or None,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        created_at=datetime.now(timezone.utc),
    ))
