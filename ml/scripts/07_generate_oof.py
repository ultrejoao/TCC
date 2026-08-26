"""Gera as predicoes out-of-fold dos dois alvos, para uso na demonstracao.

Cada janela e predita por um modelo que NAO viu o especime dela. E este o
numero honesto: o modelo de producao (06_train_production.py) e treinado com
tudo e por isso nao pode ser demonstrado sobre os proprios dados de treino.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_INTERIM  # noqa: E402
from kaist.decision import PROPORTION_NAMES, PhysicalSignature, physical_proportions  # noqa: E402
from kaist.features import model_feature_columns  # noqa: E402
from kaist.loaders import discover_sessions  # noqa: E402
from kaist.splits import leave_one_specimen_out  # noqa: E402

INDICATORS = ["iso_v_rms_mms", "iso_v_1x_mms", "iso_v_2x_mms", "iso_a_hf_g"]
SEED = 42


def main() -> None:
    df = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")
    df["fault_type"] = np.where(df.fault_family == "normal", "normal", df.fault_family)
    props = df[INDICATORS].apply(
        lambda r: physical_proportions(r.to_dict()), axis=1, result_type="expand")
    df[PROPORTION_NAMES] = props[PROPORTION_NAMES]

    X = df[model_feature_columns(df.columns)].to_numpy(dtype=np.float32)
    P = df[PROPORTION_NAMES].to_numpy()
    folds = leave_one_specimen_out(discover_sessions())

    out = df[["session_id", "specimen_id", "window_index"]].copy()

    for target, col in [("severity", "label"), ("fault_type", "fault_type")]:
        classes = sorted(df[col].unique())
        y = df[col].map({c: i for i, c in enumerate(classes)}).to_numpy()
        pred = np.full(len(df), -1)
        conf = np.zeros(len(df))

        for f in folds:
            tr = df.session_id.isin(f.train_sessions).to_numpy()
            te = df.session_id.isin(f.test_sessions).to_numpy()
            rf = RandomForestClassifier(
                n_estimators=400, max_depth=12, min_samples_leaf=3,
                class_weight="balanced", n_jobs=-1, random_state=SEED).fit(X[tr], y[tr])
            xgb = XGBClassifier(
                n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8,
                colsample_bytree=0.8, tree_method="hist", n_jobs=-1, random_state=SEED)
            xgb.fit(X[tr], y[tr], sample_weight=compute_sample_weight("balanced", y[tr]))
            proba = (rf.predict_proba(X[te]) + xgb.predict_proba(X[te])) / 2.0
            pred[te] = proba.argmax(axis=1)
            conf[te] = proba.max(axis=1)

            if target == "fault_type":   # assinatura fisica do fold, so do treino
                sig = PhysicalSignature.fit(P[tr], y[tr], classes)
                out.loc[te, "oof_physical_type"] = [classes[i] for i in sig.predict(P[te])]

        out[f"oof_{target}"] = [classes[i] for i in pred]
        out[f"oof_{target}_proba"] = conf
        print(f"  {target:12s} acuracia out-of-fold = {(pred == y).mean():.1%}", flush=True)

    dest = DATA_INTERIM / "oof_predictions.parquet"
    out.to_parquet(dest, index=False)
    print(f"\npredicoes out-of-fold salvas em {dest}")


if __name__ == "__main__":
    main()
