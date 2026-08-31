#!/bin/sh
# Prepara o ambiente antes de servir a API.
set -e

echo "[entrypoint] aguardando o banco em ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}"
until python -c "
import os, socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect((os.getenv('POSTGRES_HOST', 'db'), int(os.getenv('POSTGRES_PORT', '5432'))))
except OSError:
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done

echo "[entrypoint] aplicando migrations"
python -m alembic upgrade head

# A inferencia recusa operar com artefato nao registrado em ml_models, entao o
# registro precisa acontecer antes de a API atender qualquer medicao.
echo "[entrypoint] registrando modelos"
python scripts/register_models.py --activate kaist_full || {
  echo "[entrypoint] AVISO: nenhum artefato de modelo encontrado."
  echo "[entrypoint] O diagnostico responde 503 ate que ml/artifacts/ seja populado."
}

echo "[entrypoint] iniciando: $*"
exec "$@"
