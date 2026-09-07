"""Treina e serializa os dois perfis de instrumentacao.

`kaist_full`    4 acelerometros + corrente, 97 features
                E o modelo da metodologia e dos resultados do TCC.

`field_single`  1 canal de vibracao, 25 features
                E o modelo que opera com instrumentacao de campo.

Ambos usam o mesmo ensemble (RF + XGBoost, soft voting), o mesmo protocolo de
avaliacao (leave-one-specimen-out) e o mesmo formato de artefato, de modo que a
API trata os dois de forma intercambiavel.

As metricas gravadas nos metadados vem da VALIDACAO CRUZADA, nao deste treino:
o modelo de producao ve todos os dados e por isso nao pode ser avaliado neles.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import ARTIFACTS, DATA_INTERIM  # noqa: E402
from kaist.decision import PROPORTION_NAMES, PhysicalSignature, physical_proportions  # noqa: E402
from kaist.features import model_feature_columns  # noqa: E402
from kaist.loaders import discover_sessions  # noqa: E402
from kaist.splits import (  # noqa: E402
    HOLDOUT_NORMAL_SESSION,
    HOLDOUT_SPECIMENS,
    holdout_session_ids,
)
from signals.pipeline import PROFILE_FULL, PROFILE_SINGLE, PROFILES  # noqa: E402

SEED = 42
VERSION = "v1"

#: Duracao da janela de analise. Precisa viajar DENTRO do artefato: o preditor
#: le `bundle["window_seconds"]` para fatiar o sinal de campo exatamente como no
#: treino. Antes o valor existia so nos metadados JSON, e o preditor caia num
#: padrao de 1,0 s — inofensivo enquanto todos os perfis usam 1,0 s, e um erro
#: silencioso no dia em que um perfil usar outra janela.
WINDOW_SECONDS = 1.0
INDICATORS = ["iso_v_rms_mms", "iso_v_1x_mms", "iso_v_2x_mms", "iso_a_hf_g"]

# Metricas obtidas em 04_evaluate.py e 08_single_channel_profile.py,
# sob leave-one-specimen-out.
METRICS = {
    PROFILE_FULL: {
        "protocol": "leave-one-specimen-out",
        "fault_type_accuracy": 0.887,
        "severity_accuracy": 0.631,
        "fault_type_recall": {"bearing": 1.00, "unbalance": 0.99,
                              "normal": 0.77, "misalignment": 0.67},
        "severity_recall": {"FAILURE": 0.85, "HEALTHY": 0.71, "WARNING": 0.00},
        "leave_one_load_out": {"fault_type_accuracy": 0.806,
                               "severity_accuracy": 0.953},
    },
    PROFILE_SINGLE: {
        "protocol": "leave-one-specimen-out",
        "fault_type_accuracy": 0.854,
        "severity_accuracy": 0.561,
        "fault_type_recall": {"bearing": 1.00, "unbalance": 0.96,
                              "misalignment": 0.66, "normal": 0.59},
        "severity_recall": {"FAILURE": 0.81, "HEALTHY": 0.23, "WARNING": 0.07},
        "binary_detection": {"sensitivity": 0.937, "specificity": 0.233},
    },
}

LIMITATIONS = {
    PROFILE_FULL: [
        "Recall de WARNING = 0,0% sob leave-one-specimen-out: o dataset tem um "
        "unico especime por nivel de severidade.",
        "Especime saudavel unico: nenhuma particao avalia generalizacao para "
        "uma maquina saudavel nunca vista.",
        "Selecao de features e calibracao da matriz de decisao foram feitas "
        "sobre os mesmos folds de avaliacao (otimismo nao quantificado).",
    ],
    PROFILE_SINGLE: [
        "Reconhecimento da condicao normal e fraco (recall 59% no tipo, 23% na "
        "severidade): sem os demais canais, a magnitude e dominada pela carga.",
        "Alta sensibilidade (93,7%) com baixa especificidade (23,3%): o perfil "
        "tende a sinalizar motores saudaveis. Adequado a TRIAGEM, nao a "
        "diagnostico conclusivo de normalidade.",
        "Herda as limitacoes do perfil completo quanto a graduacao de severidade.",
    ],
}


def train_ensemble(X: np.ndarray, y: np.ndarray):
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=12, min_samples_leaf=3,
        class_weight="balanced", n_jobs=-1, random_state=SEED)
    xgb = XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, tree_method="hist", n_jobs=-1, random_state=SEED)
    rf.fit(X, y)
    xgb.fit(X, y, sample_weight=compute_sample_weight("balanced", y))
    return rf, xgb


def build_profile(profile: str, df: pd.DataFrame, feature_cols: list[str],
                  holdout: list[str]) -> Path:
    spec = PROFILES[profile]
    df = df.copy()
    df["fault_type"] = np.where(df.fault_family == "normal", "normal", df.fault_family)

    # As sessoes reservadas saem do treino. Sem isso, qualquer demonstracao
    # usaria dado ja visto e nao mostraria o comportamento real do modelo.
    total_antes = len(df)
    df = df[~df.session_id.isin(holdout)]

    X = df[feature_cols].to_numpy(dtype=np.float32)
    print(f"\n=== {profile} ===")
    print(f"  {X.shape[0]} janelas x {X.shape[1]} features "
          f"({total_antes - len(df)} janelas reservadas para demonstracao)")

    bundle = {
        "profile": profile,
        "version": VERSION,
        "requires": {
            "vibration_channels": spec.min_vibration_channels,
            "current": spec.requires_current,
        },
        # Fica gravado no artefato o que o modelo NAO viu, para que a afirmacao
        # "este defeito e inedito" seja verificavel e nao dependa de memoria.
        "holdout": {
            "specimens": list(HOLDOUT_SPECIMENS),
            "normal_session": HOLDOUT_NORMAL_SESSION,
            "sessions": holdout,
            "note": (
                "Especimes reservados: o modelo nunca viu nenhuma medicao "
                "destas montagens. A sessao normal e um hold-out mais fraco — "
                "o especime saudavel e unico no dataset, entao o modelo viu a "
                "mesma montagem sob outras cargas."),
        },
        "description": spec.description,
        "feature_columns": feature_cols,
        "indicator_columns": INDICATORS,
        "targets": {},
        "metrics": METRICS[profile],
        "known_limitations": LIMITATIONS[profile],
        "window_seconds": WINDOW_SECONDS,
    }

    for target, col in [("severity", "label"), ("fault_type", "fault_type")]:
        classes = sorted(df[col].unique())
        y = df[col].map({c: i for i, c in enumerate(classes)}).to_numpy()
        rf, xgb = train_ensemble(X, y)
        bundle["targets"][target] = {"classes": classes, "rf": rf, "xgb": xgb}
        print(f"  {target:12s} classes={classes}")

    props = df[INDICATORS].apply(
        lambda r: physical_proportions(r.to_dict()), axis=1, result_type="expand")
    ft_classes = bundle["targets"]["fault_type"]["classes"]
    y_ft = df["fault_type"].map({c: i for i, c in enumerate(ft_classes)}).to_numpy()
    bundle["physical_signature"] = PhysicalSignature.fit(
        props[PROPORTION_NAMES].to_numpy(), y_ft, ft_classes)

    destino = ARTIFACTS / f"model_{profile}_{VERSION}.joblib"
    joblib.dump(bundle, destino, compress=3)
    sha = hashlib.sha256(destino.read_bytes()).hexdigest()
    print(f"  -> {destino.name}  ({destino.stat().st_size/1e6:.1f} MB)")

    meta = {k: v for k, v in bundle.items()
            if k not in {"targets", "physical_signature"}}
    meta.update({
        "algorithm": "rf_xgb_soft_voting_ensemble",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_windows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "dataset": "KAIST (Jung et al., 2023) - 45 sessoes, 15 especimes",
        # relativo a raiz do projeto: caminho absoluto nao sobrevive ao container
        "artifact_path": destino.relative_to(ARTIFACTS.parent.parent).as_posix(),
        "artifact_sha256": sha,
        "hyperparameters": {
            "rf": {"n_estimators": 400, "max_depth": 12, "min_samples_leaf": 3,
                   "class_weight": "balanced"},
            "xgb": {"n_estimators": 400, "max_depth": 6, "learning_rate": 0.05,
                    "subsample": 0.8, "colsample_bytree": 0.8},
        },
        "evaluation_note": (
            "Metricas obtidas por validacao cruzada leave-one-specimen-out, NAO "
            "por este treino. Os protocolos estabelecem cenarios de dificuldade "
            "distintos para a generalizacao do modelo, fornecendo uma faixa de "
            "referencia metodologica para interpretar resultados futuros obtidos "
            "em dados de campo."),
    })
    (ARTIFACTS / f"model_{profile}_{VERSION}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino


def main() -> None:
    holdout = holdout_session_ids(discover_sessions())
    print(f"hold-out de demonstracao: {len(holdout)} sessoes fora do treino")
    for sid in holdout:
        print(f"  {sid}")

    completo = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")
    build_profile(PROFILE_FULL, completo,
                  model_feature_columns(completo.columns), holdout)

    single = pd.read_parquet(DATA_INTERIM / "features_single_channel.parquet")
    cols_single = [c for c in single.columns if c.startswith(("vib_", "iso_"))]
    build_profile(PROFILE_SINGLE, single, cols_single, holdout)

    print("\nartefatos em", ARTIFACTS)


if __name__ == "__main__":
    main()
