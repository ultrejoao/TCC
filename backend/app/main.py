"""Aplicacao FastAPI.

Camadas de seguranca aplicadas globalmente:
  * CORS explicito, restrito as origens configuradas (nunca "*" com credenciais)
  * rate limiting, mais estrito nos endpoints de autenticacao
  * erros padronizados no estilo RFC 7807
  * cabecalhos de seguranca em toda resposta
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.routes import auth, measurements, motors
from app.config import get_settings
from app.core.errors import (
    CONTENT_TYPE,
    ProblemException,
    http_exception_handler,
    problem_exception_handler,
    validation_exception_handler,
)

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model_bundle = None       # carregado sob demanda na inferencia
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "API do sistema de predicao de falhas em motores eletricos industriais. "
        "O tecnico envia o sinal coletado em campo e recebe o diagnostico na "
        "mesma requisicao."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter

# --- CORS -------------------------------------------------------------------
# allow_credentials=True exige lista explicita de origens: o navegador recusa
# "*" quando cookies estao envolvidos, e permitir tudo anularia a protecao.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


# --- tratamento de erros ----------------------------------------------------
app.add_exception_handler(ProblemException, problem_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        media_type=CONTENT_TYPE,
        content={
            "type": "about:blank",
            "title": "Requisicoes em excesso",
            "status": status.HTTP_429_TOO_MANY_REQUESTS,
            "detail": "Limite de requisicoes excedido. Tente novamente em instantes.",
            "instance": str(request.url.path),
        },
    )


# --- rotas ------------------------------------------------------------------
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(motors.router, prefix=settings.api_v1_prefix)
app.include_router(measurements.router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["infraestrutura"])
def health() -> dict:
    return {"status": "ok"}
