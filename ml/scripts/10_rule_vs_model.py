"""Regra de analise de vibracao contra modelo, na identificacao do tipo de falha.

Pergunta que este experimento responde
--------------------------------------
Se a analise de assinatura espectral ja e conhecimento consolidado — 1x a
rotacao indica desbalanceamento, 2x indica desalinhamento, alta frequencia
indica rolamento — qual e a contribuicao de um modelo de aprendizado?

E a pergunta que uma banca faz, e ela merece resposta medida, nao argumentada.

Tres metodos, mesmo protocolo (leave-one-specimen-out), mesmo alvo:

  A) REGRA DE LIVRO      a proporcao espectral mais destacada define o tipo,
                         conforme a associacao classica da literatura.
  B) REGRA EMPIRICA      protótipos das mesmas proporcoes, porem AJUSTADOS aos
                         dados de treino de cada fold, em vez de transcritos da
                         teoria.
  C) ENSEMBLE            Random Forest + XGBoost sobre as 97 features.

O que se espera aprender: quanto da tarefa a teoria classica resolve sozinha, e
onde ela falha neste dataset especifico.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_INTERIM  # noqa: E402
from kaist.decision import PROPORTION_NAMES, PhysicalSignature, physical_proportions  # noqa: E402
from kaist.features import model_feature_columns  # noqa: E402
from kaist.loaders import discover_sessions  # noqa: E402
from kaist.splits import leave_one_specimen_out  # noqa: E402

INDICATORS = ["iso_v_rms_mms", "iso_v_1x_mms", "iso_v_2x_mms", "iso_a_hf_g"]

#: Associacao classica da analise de vibracao entre componente espectral e falha.
REGRA_CLASSICA = {"p_1x": "unbalance", "p_2x": "misalignment", "p_hf": "bearing"}

#: Abaixo deste destaque sobre a mediana, nenhuma componente se sobressai e a
#: condicao e tratada como normal.
LIMIAR_DESTAQUE = 1.25
SEED = 42


def regra_de_livro(df: pd.DataFrame) -> np.ndarray:
    """Classifica pela proporcao espectral mais destacada, conforme a teoria."""
    normalizado = df[PROPORTION_NAMES] / df[PROPORTION_NAMES].median()
    predito = normalizado.idxmax(axis=1).map(REGRA_CLASSICA)
    predito[normalizado.max(axis=1) < LIMIAR_DESTAQUE] = "normal"
    return predito.to_numpy()


def regra_empirica(df, P, y, labels, folds) -> np.ndarray:
    """Protótipos das proporcoes, ajustados apenas no treino de cada fold."""
    pred = np.full(len(df), -1)
    for f in folds:
        tr = df.session_id.isin(f.train_sessions).to_numpy()
        te = df.session_id.isin(f.test_sessions).to_numpy()
        assinatura = PhysicalSignature.fit(P[tr], y[tr], labels)
        pred[te] = assinatura.predict(P[te])
    return pred


def modelo(df, X, y, folds) -> np.ndarray:
    pred = np.full(len(df), -1)
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
        pred[te] = ((rf.predict_proba(X[te]) + xgb.predict_proba(X[te])) / 2).argmax(1)
    return pred


def main() -> None:
    df = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")
    df["fam"] = np.where(df.fault_family == "normal", "normal", df.fault_family)

    props = df[INDICATORS].apply(
        lambda r: physical_proportions(r.to_dict()), axis=1, result_type="expand")
    df[PROPORTION_NAMES] = props[PROPORTION_NAMES]

    labels = sorted(df.fam.unique())
    y = df.fam.map({c: i for i, c in enumerate(labels)}).to_numpy()
    X = df[model_feature_columns(df.columns)].to_numpy(dtype=np.float32)
    P = df[PROPORTION_NAMES].to_numpy()
    folds = leave_one_specimen_out(discover_sessions())

    print(f"{len(df)} janelas · protocolo leave-one-specimen-out ({len(folds)} folds)\n")

    livro = regra_de_livro(df)
    empirica = regra_empirica(df, P, y, labels, folds)
    ml = modelo(df, X, y, folds)

    resultados = {
        "regra de livro (1x/2x/HF)": (livro == df.fam.to_numpy()),
        "regra empirica (protótipos)": (empirica == y),
        "ensemble RF + XGBoost": (ml == y),
    }

    print("=" * 66)
    print("ACURACIA NA IDENTIFICACAO DO TIPO DE FALHA")
    print("=" * 66)
    for nome, acertos in resultados.items():
        print(f"  {nome:32s} {acertos.mean():6.1%}")

    print("\n" + "=" * 66)
    print("RECALL POR FAMILIA")
    print("=" * 66)
    print(f"{'familia':16s} {'livro':>10s} {'empirica':>10s} {'modelo':>10s}")
    for i, fam in enumerate(labels):
        m = y == i
        print(f"{fam:16s} {(livro[m] == fam).mean():10.1%} "
              f"{(empirica[m] == i).mean():10.1%} {(ml[m] == i).mean():10.1%}")

    print("\n" + "=" * 66)
    print("ONDE A REGRA DE LIVRO ERRA (matriz de confusao)")
    print("=" * 66)
    cm = confusion_matrix(df.fam, livro, labels=labels)
    print(pd.DataFrame(cm, index=labels, columns=labels).to_string())

    print("\n" + "=" * 66)
    print("POR QUE A ASSINATURA CLASSICA FALHA AQUI")
    print("=" * 66)
    med = df.groupby("fam")[PROPORTION_NAMES].median().round(3)
    print(med.to_string())
    print()
    p2x_norm = med.loc["normal", "p_2x"]
    p2x_mis = med.loc["misalignment", "p_2x"]
    print(f"A literatura associa desalinhamento a pico em 2x. Neste dataset o")
    print(f"p_2x do desalinhamento ({p2x_mis:.3f}) e MENOR que o da condicao")
    print(f"normal ({p2x_norm:.3f}) — a regra procura no lugar errado, e o")
    print(f"desalinhamento se manifesta na alta frequencia.")

    saida = pd.DataFrame({
        "metodo": list(resultados),
        "acuracia": [a.mean() for a in resultados.values()],
    })
    destino = DATA_INTERIM / "rule_vs_model.csv"
    saida.to_csv(destino, index=False)
    print(f"\nresumo salvo em {destino}")


if __name__ == "__main__":
    main()
