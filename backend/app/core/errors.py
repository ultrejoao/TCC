"""Erros padronizados no estilo RFC 7807 (Problem Details).

Toda resposta de erro tem o mesmo formato, com content-type
application/problem+json, para que o frontend trate erros de forma uniforme.
"""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

CONTENT_TYPE = "application/problem+json"


class ProblemException(HTTPException):
    def __init__(self, status_code: int, title: str, detail: str,
                 type_: str = "about:blank", **extra: Any) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.title = title
        self.type_ = type_
        self.extra = extra


def _problem(status_code: int, title: str, detail: str, instance: str,
             type_: str = "about:blank", **extra: Any) -> JSONResponse:
    body = {"type": type_, "title": title, "status": status_code,
            "detail": detail, "instance": instance}
    body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type=CONTENT_TYPE)


async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
    return _problem(exc.status_code, exc.title, str(exc.detail),
                    str(request.url.path), exc.type_, **exc.extra)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    titulos = {
        400: "Requisicao invalida", 401: "Nao autenticado", 403: "Acesso negado",
        404: "Recurso nao encontrado", 409: "Conflito",
        413: "Conteudo grande demais", 415: "Formato nao suportado",
        422: "Dados invalidos", 429: "Requisicoes em excesso",
        500: "Erro interno",
    }
    return _problem(exc.status_code, titulos.get(exc.status_code, "Erro"),
                    str(exc.detail), str(request.url.path))


async def validation_exception_handler(request: Request,
                                       exc: RequestValidationError) -> JSONResponse:
    erros = [{"campo": ".".join(str(p) for p in e["loc"][1:]), "mensagem": e["msg"]}
             for e in exc.errors()]
    return _problem(status.HTTP_422_UNPROCESSABLE_ENTITY, "Dados invalidos",
                    "Um ou mais campos da requisicao sao invalidos.",
                    str(request.url.path), errors=erros)
