"""Avaliacao do ensemble RF + XGBoost nos dois alvos e nos dois protocolos.

Alvos
-----
  severity    HEALTHY / WARNING / FAILURE      (objetivo do TCC)
  fault_type  normal / bearing / misalignment / unbalance
              (alimenta a explicabilidade: "padrao consistente com desalinhamento")

Protocolos
----------
  leave-one-specimen-out  isola a montagem fisica; defeito de tipo e grau ineditos
  leave-one-load-out      isola a condicao de carga; o especime e compartilhado
                          entre treino e teste — vazamento DECLARADO, nao ignorado

Os dois protocolos estabelecem cenarios de dificuldade distintos para a
generalizacao do modelo, fornecendo uma faixa de referencia metodologica para
interpretar resultados futuros obtidos em dados de campo. NAO se deve inferir
deles que o desempenho em campo ficara entre os dois valores: isso depende da
distribuicao real dos motores monitorados.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_INTERIM  # noqa: E402
from kaist.features import model_feature_columns  # noqa: E402
from kaist.loaders import discover_sessions  # noqa: E402
from kaist.splits import leave_one_specimen_out  # noqa: E402

SEED = 42


def build_models(n_classes: int):
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=12, min_samples_leaf=3,
        class_weight="balanced", n_jobs=-1, random_state=SEED)
    xgb = XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, tree_method="hist", n_jobs=-1, random_state=SEED)
    return rf, xgb


def fit_predict(X, y, tr, te):
    rf, xgb = build_models(len(np.unique(y)))
    rf.fit(X[tr], y[tr])
    xgb.fit(X[tr], y[tr], sample_weight=compute_sample_weight("balanced", y[tr]))
    return (rf.predict_proba(X[te]) + xgb.predict_proba(X[te])) / 2.0


def specimen_folds(df, sessions):
    for f in leave_one_specimen_out(sessions):
        yield (f.held_out_specimen,
               df.session_id.isin(f.train_sessions).to_numpy(),
               df.session_id.isin(f.test_sessions).to_numpy())


def load_folds(df, _sessions):
    for load in sorted(df.load_nm.unique()):
        te = (df.load_nm == load).to_numpy()
        yield (f"carga {load} Nm", ~te, te)


def evaluate(df, X, target, folds_fn, sessions, nome):
    labels = sorted(df[target].unique())
    mapping = {c: i for i, c in enumerate(labels)}
    y = df[target].map(mapping).to_numpy()

    oof = np.full(len(df), -1, dtype=int)
    for _, tr, te in folds_fn(df, sessions):
        oof[te] = fit_predict(X, y, tr, te).argmax(axis=1)
    assert (oof >= 0).all(), "janela sem predicao out-of-fold"

    acc = float(np.mean(oof == y))
    cm = confusion_matrix(y, oof, labels=range(len(labels)))
    print(f"\n{'=' * 74}\n{nome}   |   acuracia = {acc:.1%}\n{'=' * 74}")
    print(pd.DataFrame(cm, index=labels, columns=labels).to_string())
    print()
    print(classification_report(y, oof, target_names=labels, digits=3, zero_division=0))
    return {"alvo": target, "protocolo": nome, "acuracia": acc,
            "recalls": {labels[i]: float(cm[i, i] / max(cm[i].sum(), 1))
                        for i in range(len(labels))}}


def main() -> None:
    df = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")
    sessions = discover_sessions()

    df["severity"] = df["label"]
    df["fault_type"] = np.where(df.fault_family == "normal", "normal", df.fault_family)

    cols = model_feature_columns(df.columns)
    X = df[cols].to_numpy(dtype=np.float32)
    print(f"matriz: {X.shape[0]} janelas x {X.shape[1]} features")

    resultados = []
    for target in ["severity", "fault_type"]:
        for folds_fn, pname in [(specimen_folds, "leave-one-specimen-out"),
                                (load_folds, "leave-one-load-out (vazamento declarado)")]:
            resultados.append(
                evaluate(df, X, target, folds_fn, sessions, f"{target} | {pname}"))

    print(f"\n{'=' * 74}\nRESUMO\n{'=' * 74}")
    resumo = pd.DataFrame([
        {"alvo": r["alvo"], "protocolo": r["protocolo"].split("| ")[1],
         "acuracia": f"{r['acuracia']:.1%}",
         **{k: f"{v:.1%}" for k, v in r["recalls"].items()}}
        for r in resultados])
    print(resumo.to_string(index=False))
    resumo.to_csv(DATA_INTERIM / "evaluation_summary.csv", index=False)
    print(f"\nresumo salvo em {DATA_INTERIM / 'evaluation_summary.csv'}")


if __name__ == "__main__":
    main()
