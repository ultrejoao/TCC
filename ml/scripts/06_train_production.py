"""Treina o modelo de producao e serializa para uso pelo sistema.

Diferenca em relacao a 04_evaluate.py: aqui o modelo e treinado com TODAS as 45
sessoes, pois e o artefato que ira para producao. As METRICAS reportadas nao vem
deste treino — vem da validacao cruzada por especime (04_evaluate.py), como deve
ser. O modelo treinado em tudo nao pode ser avaliado em nada.

Gera em ml/artifacts/:
    model_v1.joblib     ensembles + assinatura fisica + lista de features
    model_v1.json       metadados para a tabela ml_models do banco
"""

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
from kaist.decision import (  # noqa: E402
    PROPORTION_NAMES,
    PhysicalSignature,
    physical_proportions,
)
from kaist.features import model_feature_columns  # noqa: E402

MODEL_VERSION = "v1"
SEED = 42
INDICATORS = ["iso_v_rms_mms", "iso_v_1x_mms", "iso_v_2x_mms", "iso_a_hf_g"]


def train_ensemble(X, y):
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=12, min_samples_leaf=3,
        class_weight="balanced", n_jobs=-1, random_state=SEED)
    xgb = XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, tree_method="hist", n_jobs=-1, random_state=SEED)
    rf.fit(X, y)
    xgb.fit(X, y, sample_weight=compute_sample_weight("balanced", y))
    return rf, xgb


def main() -> None:
    df = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")
    df["fault_type"] = np.where(df.fault_family == "normal", "normal", df.fault_family)

    feat_cols = model_feature_columns(df.columns)
    X = df[feat_cols].to_numpy(dtype=np.float32)
    print(f"treinando com {X.shape[0]} janelas x {X.shape[1]} features\n")

    bundle = {"version": MODEL_VERSION, "feature_columns": feat_cols,
              "indicator_columns": INDICATORS, "targets": {}}

    for target in ["severity", "fault_type"]:
        col = "label" if target == "severity" else target
        classes = sorted(df[col].unique())
        y = df[col].map({c: i for i, c in enumerate(classes)}).to_numpy()
        print(f"  {target:12s} classes={classes}")
        rf, xgb = train_ensemble(X, y)
        bundle["targets"][target] = {"classes": classes, "rf": rf, "xgb": xgb}

    # assinatura fisica ajustada em todos os dados (parte do artefato de producao)
    props = df[INDICATORS].apply(
        lambda r: physical_proportions(r.to_dict()), axis=1, result_type="expand")
    ft_classes = bundle["targets"]["fault_type"]["classes"]
    y_ft = df["fault_type"].map({c: i for i, c in enumerate(ft_classes)}).to_numpy()
    bundle["physical_signature"] = PhysicalSignature.fit(
        props[PROPORTION_NAMES].to_numpy(), y_ft, ft_classes)

    out = ARTIFACTS / f"model_{MODEL_VERSION}.joblib"
    joblib.dump(bundle, out, compress=3)
    print(f"\nmodelo salvo em {out}  ({out.stat().st_size/1e6:.1f} MB)")

    # metadados -> futura tabela ml_models
    summary = pd.read_csv(DATA_INTERIM / "evaluation_summary.csv")
    meta = {
        "version": MODEL_VERSION,
        "algorithm": "rf_xgb_soft_voting_ensemble",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_windows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "window_seconds": 1.0,
        "dataset": "KAIST (Jung et al., 2023) - 45 sessoes, 15 especimes",
        "hyperparameters": {
            "rf": {"n_estimators": 400, "max_depth": 12, "min_samples_leaf": 3,
                   "class_weight": "balanced"},
            "xgb": {"n_estimators": 400, "max_depth": 6, "learning_rate": 0.05,
                    "subsample": 0.8, "colsample_bytree": 0.8},
        },
        "evaluation": summary.to_dict(orient="records"),
        "evaluation_note": (
            "Metricas obtidas por validacao cruzada (04_evaluate.py), NAO por "
            "este treino. Os dois protocolos estabelecem cenarios de dificuldade "
            "distintos para a generalizacao do modelo, fornecendo uma faixa de "
            "referencia metodologica para interpretar resultados futuros obtidos "
            "em dados de campo."),
        "known_limitations": [
            "Recall de WARNING = 0,0% sob leave-one-specimen-out: o dataset tem "
            "um unico especime por nivel de severidade.",
            "Especime saudavel unico: nenhuma particao avalia generalizacao para "
            "uma maquina saudavel nunca vista.",
            "Selecao de features e calibracao da matriz de decisao foram feitas "
            "sobre os mesmos folds de avaliacao (otimismo nao quantificado).",
        ],
    }
    meta_path = ARTIFACTS / f"model_{MODEL_VERSION}.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"metadados salvos em {meta_path}")


if __name__ == "__main__":
    main()
