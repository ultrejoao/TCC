"""Calibra a margem de concordancia da matriz de decisao.

Objetivo: escolher quanto o sistema sinaliza. Margem pequena sinaliza muito; margem grande sinaliza pouco. O criterio e o
ganho: quanto a taxa de erro sobe entre as janelas sinalizadas em relacao as
nao sinalizadas, e que fracao dos erros totais e capturada.
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

IND = ["iso_v_rms_mms", "iso_v_1x_mms", "iso_v_2x_mms", "iso_a_hf_g"]


def main() -> None:
    df = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")
    df["fam"] = np.where(df.fault_family == "normal", "normal", df.fault_family)
    props = df[IND].apply(lambda r: physical_proportions(r.to_dict()),
                          axis=1, result_type="expand")
    df[PROPORTION_NAMES] = props[PROPORTION_NAMES]

    labs = sorted(df.fam.unique())
    y = df.fam.map({c: i for i, c in enumerate(labs)}).to_numpy()
    X = df[model_feature_columns(df.columns)].to_numpy(dtype=np.float32)
    P = df[PROPORTION_NAMES].to_numpy()

    ml_pred = np.full(len(df), -1)
    gap = np.full(len(df), np.nan)      # distancia extra da classe predita

    for f in leave_one_specimen_out(discover_sessions()):
        tr = df.session_id.isin(f.train_sessions).to_numpy()
        te = df.session_id.isin(f.test_sessions).to_numpy()

        rf = RandomForestClassifier(n_estimators=300, max_depth=12, min_samples_leaf=3,
                                    class_weight="balanced", n_jobs=-1,
                                    random_state=42).fit(X[tr], y[tr])
        xg = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=.05,
                           subsample=.8, colsample_bytree=.8, tree_method="hist",
                           n_jobs=-1, random_state=42)
        xg.fit(X[tr], y[tr], sample_weight=compute_sample_weight("balanced", y[tr]))
        pred = ((rf.predict_proba(X[te]) + xg.predict_proba(X[te])) / 2).argmax(1)
        ml_pred[te] = pred

        sig = PhysicalSignature.fit(P[tr], y[tr], labs)   # protótipos so do treino
        d = sig.distances(P[te])
        gap[te] = d[np.arange(len(pred)), pred] - d.min(axis=1)

    erro = ml_pred != y
    print(f"acuracia global do modelo: {(~erro).mean():.1%}   erros: {erro.sum()}\n")
    print(f"{'margem':>7} {'sinalizado':>11} {'erro sinaliz.':>14} {'erro nao sin.':>14} "
          f"{'ganho':>7} {'erros capturados':>17}")
    for margin in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
        flag = gap > margin                      # discordante = sinalizado
        if flag.sum() == 0 or (~flag).sum() == 0:
            continue
        e_flag, e_ok = erro[flag].mean(), erro[~flag].mean()
        capt = erro[flag].sum() / max(erro.sum(), 1)
        print(f"{margin:7.2f} {flag.mean():10.1%} {e_flag:13.1%} {e_ok:13.1%} "
              f"{e_flag / max(e_ok, 1e-9):6.1f}x {capt:16.0%}")

    print("\nleitura: 'ganho' = quantas vezes a taxa de erro e maior entre as")
    print("janelas sinalizadas. Escolher a margem que capture uma fracao util")
    print("dos erros sem sinalizar volume excessivo.")


if __name__ == "__main__":
    main()
