"""Hash de senha (argon2id), JWT em cookie httpOnly e CSRF por double-submit."""

import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.config import get_settings

settings = get_settings()

# Parametros acima do minimo da OWASP (19 MiB, t=2, p=1).
_hasher = PasswordHasher(
    time_cost=3,          # iteracoes
    memory_cost=65536,    # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

TokenType = Literal["access", "refresh"]


# --------------------------------------------------------------------------
# senha
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Verifica a senha.

    Retorna (valida, novo_hash). O `novo_hash` vem preenchido quando os
    parametros de custo mudaram desde o cadastro
    """
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False, None

    novo = _hasher.hash(password) if _hasher.check_needs_rehash(password_hash) else None
    return True, novo


def password_issues(password: str) -> list[str]:
    """Politica minima de senha. Retorna a lista de problemas encontrados."""
    problemas = []
    if len(password) < 12:
        problemas.append("deve ter ao menos 12 caracteres")
    if not any(c.isalpha() for c in password):
        problemas.append("deve conter ao menos uma letra")
    if not any(c.isdigit() for c in password):
        problemas.append("deve conter ao menos um numero")
    return problemas


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------
def _create_token(subject: str, token_type: TokenType, expires: timedelta,
                  extra: dict[str, Any] | None = None) -> str:
    agora = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": agora,
        "exp": agora + expires,
        "jti": str(uuid.uuid4()),      # identificador unico, permite revogacao
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID | str, role: str) -> str:
    return _create_token(
        str(user_id), "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        {"role": role})


def create_refresh_token(user_id: uuid.UUID | str) -> tuple[str, str, datetime]:
    """Retorna (token, jti, expira_em)."""
    agora = datetime.now(timezone.utc)
    expira = agora + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": str(user_id), "type": "refresh", "iat": agora, "exp": expira, "jti": jti},
        settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expira


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decodifica e valida. Levanta jwt.InvalidTokenError se algo nao conferir."""
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub", "type", "jti"]})
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"tipo de token invalido: esperado '{expected_type}'")
    return payload


# --------------------------------------------------------------------------
# CSRF (double-submit token)
# --------------------------------------------------------------------------
def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_tokens_match(cookie_token: str | None, header_token: str | None) -> bool:
    """Comparacao em tempo constante, para nao vazar informacao por timing."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)
