# Backend FastAPI com a camada de ML embutida.
#
# O modelo roda no mesmo processo da API, e nao em servico separado. Para um
# sistema deste porte, um servico de ML apartado acrescentaria uma chamada de
# rede e um ponto de falha no caminho critico do diagnostico, sem ganho: a
# inferencia leva ~170 ms e nao concorre por GPU. O isolamento que importa e
# logico — app/ml/ nao conhece detalhe de API, e app/api/ nao conhece detalhe
# de modelo — o que mantem a extracao para um servico proprio como refatoracao
# local, caso o volume justifique.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libgomp e exigida pelo XGBoost em runtime; sem ela o import falha.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# As dependencias mudam bem menos que o codigo: copiadas antes para que a
# camada de instalacao seja reaproveitada entre builds.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# A estrutura relativa entre backend/ e ml/ precisa ser preservada: a camada de
# inferencia importa o MESMO codigo de extracao de features usado no treino,
# resolvendo o caminho a partir da raiz do projeto.
COPY ml/ /app/ml/
COPY backend/ /app/backend/

# Executar como usuario sem privilegios: um comprometimento da aplicacao nao
# deve render root no container.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/backend/uploads \
    && chown -R app:app /app
USER app

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
