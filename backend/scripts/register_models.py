"""Registra os artefatos de modelo na tabela `ml_models`.

Toda previsao referencia o modelo que a gerou. Sem este registro, a API nao tem
como gravar a rastreabilidade — e por isso a inferencia recusa operar com um
artefato nao registrado.

O hash SHA-256 do arquivo e gravado junto: se o artefato em disco for
substituido sem passar por aqui, a divergencia e detectavel.

Uso:
    python scripts/register_models.py
    python scripts/register_models.py --activate kaist_full
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.ml_model import MLModel  # noqa: E402

settings = get_settings()
ARTIFACTS_DIR = settings.model_artifact.parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def register(db, meta_path: Path) -> MLModel:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    artefato = Path(meta["artifact_path"])
    if not artefato.exists():
        artefato = ARTIFACTS_DIR / artefato.name
    if not artefato.exists():
        raise FileNotFoundError(f"artefato ausente: {meta['artifact_path']}")

    versao = f"{meta['profile']}_{meta['version']}"
    digest = sha256(artefato)

    existente = db.scalar(select(MLModel).where(MLModel.version == versao))
    if existente:
        if existente.artifact_sha256 == digest:
            print(f"  {versao:22s} ja registrado (hash confere)")
            return existente
        print(f"  {versao:22s} artefato MUDOU — atualizando registro")
        alvo = existente
    else:
        alvo = MLModel(version=versao)
        db.add(alvo)

    alvo.algorithm = meta["algorithm"]
    alvo.hyperparameters = meta["hyperparameters"]
    alvo.metrics = meta["metrics"]
    alvo.feature_columns = meta["feature_columns"]
    alvo.dataset = meta["dataset"]
    alvo.n_windows = meta["n_windows"]
    alvo.n_features = meta["n_features"]
    alvo.window_seconds = meta["window_seconds"]
    alvo.trained_at = datetime.fromisoformat(meta["trained_at"])
    alvo.artifact_path = str(artefato)
    alvo.artifact_sha256 = digest
    alvo.known_limitations = meta["known_limitations"]
    alvo.notes = f"{meta['description']} | {meta['evaluation_note']}"

    if not existente:
        print(f"  {versao:22s} registrado ({meta['n_features']} features)")
    return alvo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activate", help="perfil a marcar como ativo")
    args = parser.parse_args()

    metas = sorted(ARTIFACTS_DIR.glob("model_*_v*.json"))
    if not metas:
        print(f"[erro] nenhum metadado em {ARTIFACTS_DIR}")
        print("       rode antes: python ml/scripts/09_train_profiles.py")
        return 1

    with SessionLocal() as db:
        print(f"registrando {len(metas)} artefato(s):")
        registrados = [register(db, m) for m in metas]

        if args.activate:
            alvo = f"{args.activate}_v1"
            achou = False
            for m in registrados:
                m.is_active = m.version == alvo
                achou = achou or m.is_active
            if not achou:
                print(f"[erro] perfil '{args.activate}' nao encontrado")
                return 1
            print(f"\nmodelo ativo: {alvo}")

        db.commit()

    print("\nok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
