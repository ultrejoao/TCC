"""Endpoints de autenticacao.

Fluxo: login -> cookies httpOnly (access + refresh) + cookie CSRF legivel.
A renovacao usa rotacao: cada refresh invalida o token anterior. Se um token ja
usado reaparece, toda a familia daquele usuario e revogada.
"""

from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    CurrentUser,
    audit,
    client_ip,
    require_csrf,
)
from app.core.errors import ProblemException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, PasswordChange, UserOut

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["autenticacao"])

DbSession = Annotated[Session, Depends(get_db)]


def _set_auth_cookies(response: Response, access: str, refresh: str, csrf: str) -> None:
    comum = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }
    response.set_cookie(
        ACCESS_COOKIE, access, path="/",
        max_age=settings.access_token_expire_minutes * 60, **comum)
    # o refresh so trafega no caminho de renovacao, reduzindo a exposicao
    response.set_cookie(
        REFRESH_COOKIE, refresh, path=f"{settings.api_v1_prefix}/auth",
        max_age=settings.refresh_token_expire_days * 86400, **comum)
    # o cookie CSRF e legivel por JavaScript de proposito: o frontend precisa
    # ler o valor para repeti-lo no cabecalho X-CSRF-Token
    response.set_cookie(
        CSRF_COOKIE, csrf, path="/", httponly=False,
        secure=settings.cookie_secure, samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _emitir_sessao(db: Session, request: Request, user: User,
                   response: Response) -> tuple[LoginResponse, str]:
    """Emite access + refresh + CSRF. Retorna a resposta e o jti do refresh."""
    access = create_access_token(user.id, user.role)
    refresh, jti, expira = create_refresh_token(user.id)
    csrf = generate_csrf_token()

    db.add(RefreshToken(
        user_id=user.id, jti=jti, expires_at=expira,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent")))

    _set_auth_cookies(response, access, refresh, csrf)
    resultado = LoginResponse(
        access_token=access,
        expires_in=settings.access_token_expire_minutes * 60,
        csrf_token=csrf,
        user=UserOut.model_validate(user))
    return resultado, jti


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response,
          db: DbSession) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))

    # Mensagem identica para e-mail inexistente e senha errada: revelar qual dos
    # dois falhou permitiria enumerar usuarios validos.
    falha = ProblemException(status.HTTP_401_UNAUTHORIZED, "Nao autenticado",
                             "E-mail ou senha invalidos.")
    if user is None:
        raise falha

    valida, novo_hash = verify_password(payload.password, user.password_hash)
    if not valida:
        audit(db, request, user, "login_failed")
        db.commit()
        raise falha

    if not user.is_active:
        raise ProblemException(status.HTTP_403_FORBIDDEN, "Acesso negado",
                               "Usuario inativo. Procure o administrador.")

    if novo_hash:                       # parametros de custo mudaram desde o cadastro
        user.password_hash = novo_hash
    user.last_login_at = datetime.now(timezone.utc)

    resultado, _ = _emitir_sessao(db, request, user, response)
    audit(db, request, user, "login_success")
    db.commit()
    return resultado


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: Request, response: Response, db: DbSession,
            refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
            ) -> LoginResponse:
    if not refresh_token:
        raise ProblemException(status.HTTP_401_UNAUTHORIZED, "Nao autenticado",
                               "Refresh token ausente.")
    try:
        payload = decode_token(refresh_token, "refresh")
    except jwt.InvalidTokenError:
        raise ProblemException(status.HTTP_401_UNAUTHORIZED, "Nao autenticado",
                               "Refresh token invalido ou expirado.") from None

    agora = datetime.now(timezone.utc)
    registro = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    if registro is None:
        raise ProblemException(status.HTTP_401_UNAUTHORIZED, "Nao autenticado",
                               "Refresh token desconhecido.")

    # DETECCAO DE REUSO: um token ja revogado reaparecendo indica que ele vazou.
    # Revoga-se toda a familia do usuario, forcando novo login.
    if registro.revoked_at is not None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == registro.user_id,
                   RefreshToken.revoked_at.is_(None))
            .values(revoked_at=agora, revoked_reason="reuse_detected"))
        audit(db, request, registro.user, "refresh_reuse_detected",
              entity="refresh_tokens", entity_id=registro.id)
        db.commit()
        _clear_auth_cookies(response)
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED, "Sessao revogada",
            "Reuso de refresh token detectado. Todas as sessoes foram encerradas "
            "por seguranca. Faca login novamente.")

    if not registro.is_usable(agora):
        raise ProblemException(status.HTTP_401_UNAUTHORIZED, "Nao autenticado",
                               "Refresh token expirado.")

    user = db.get(User, registro.user_id)
    if user is None or not user.is_active:
        raise ProblemException(status.HTTP_401_UNAUTHORIZED, "Nao autenticado",
                               "Usuario inexistente ou inativo.")

    # rotacao: o token usado e revogado e encadeado ao que o substituiu
    resultado, novo_jti = _emitir_sessao(db, request, user, response)
    registro.revoked_at = agora
    registro.revoked_reason = "rotated"
    registro.replaced_by_jti = novo_jti
    db.commit()
    return resultado


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: DbSession, user: CurrentUser,
           refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
           ) -> None:
    """Encerra a sessao atual, revogando o refresh token de fato."""
    if refresh_token:
        try:
            jti = decode_token(refresh_token, "refresh")["jti"]
            db.execute(
                update(RefreshToken)
                .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=datetime.now(timezone.utc), revoked_reason="logout"))
        except jwt.InvalidTokenError:
            pass                        # token ja invalido: encerrar mesmo assim
    audit(db, request, user, "logout")
    db.commit()
    _clear_auth_cookies(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_csrf)])
def logout_all(request: Request, response: Response, db: DbSession,
               user: CurrentUser) -> None:
    """Encerra TODAS as sessoes do usuario, em todos os dispositivos."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc), revoked_reason="logout_all"))
    audit(db, request, user, "logout_all")
    db.commit()
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_csrf)])
def change_password(payload: PasswordChange, request: Request, response: Response,
                    db: DbSession, user: CurrentUser) -> None:
    valida, _ = verify_password(payload.current_password, user.password_hash)
    if not valida:
        raise ProblemException(status.HTTP_400_BAD_REQUEST, "Requisicao invalida",
                               "Senha atual incorreta.")

    user.password_hash = hash_password(payload.new_password)
    # trocar a senha derruba todas as sessoes: e o comportamento esperado quando
    # a troca foi motivada por suspeita de comprometimento
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc),
                revoked_reason="password_changed"))
    audit(db, request, user, "password_changed")
    db.commit()
    _clear_auth_cookies(response)
