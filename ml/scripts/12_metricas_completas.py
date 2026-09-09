"""Dispersao entre folds, metricas por classe, macro-F1 e MCC.

Entrada: ml/data/interim/{features_1s,oof_predictions}.parquet
Saida:   ml/data/interim/metricas_*.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_recall_fscore_support,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_INTERIM  # noqa: E402
from kaist.loaders import discover_sessions  # noqa: E402
from kaist.splits import leave_one_specimen_out  # noqa: E402

#: Os dois alvos, com o papel de cada um deixado explicito: o tipo e a saida de
#: producao; a severidade por ML e o experimento preliminar preservado, ja que
#: em producao ela vem do criterio fisico (ISO 10816).
ALVOS = {
    "fault_type": ("TIPO DE FALHA", "saida de producao do modelo"),
    "severity": ("SEVERIDADE (ML)", "experimento preliminar — em producao vem da ISO"),
}


def carregar() -> pd.DataFrame:
    """Junta rotulos verdadeiros e predicoes out-of-fold, e marca o fold."""
    verdade = pd.read_parquet(DATA_INTERIM / "features_1s.parquet")
    oof = pd.read_parquet(DATA_INTERIM / "oof_predictions.parquet")

    if len(verdade) != len(oof) or not (verdade.session_id.values == oof.session_id.values).all():
        raise SystemExit(
            "features_1s e oof_predictions estao dessincronizados. "
            "Rode ml/scripts/07_generate_oof.py novamente.")

    df = pd.DataFrame({
        "session_id": verdade.session_id,
        "specimen_id": verdade.specimen_id,
        # o alvo 'tipo' agrupa as familias; 'normal' permanece como esta
        "fault_type_real": np.where(verdade.fault_family == "normal",
                                    "normal", verdade.fault_family),
        "fault_type_pred": oof.oof_fault_type,
        "severity_real": verdade.label,
        "severity_pred": oof.oof_severity,
    })

    # cada sessao pertence a exatamente um fold (invariante validada em splits.py)
    de_sessao_para_fold = {
        s: f.index for f in leave_one_specimen_out(discover_sessions())
        for s in f.test_sessions
    }
    df["fold"] = df.session_id.map(de_sessao_para_fold)
    df["especime_reservado"] = df.session_id.map({
        s: f.held_out_specimen
        for f in leave_one_specimen_out(discover_sessions())
        for s in f.test_sessions
    })
    return df


def por_fold(df: pd.DataFrame, alvo: str) -> pd.DataFrame:
    """Acuracia de cada fold: a base da dispersao."""
    linhas = []
    for fold, g in df.groupby("fold", sort=True):
        acertos = (g[f"{alvo}_real"] == g[f"{alvo}_pred"])
        linhas.append({
            "fold": int(fold),
            "especime_reservado": g.especime_reservado.iloc[0],
            "n_janelas": len(g),
            "acuracia": float(acertos.mean()),
        })
    return pd.DataFrame(linhas)


def por_classe(df: pd.DataFrame, alvo: str) -> pd.DataFrame:
    """Precisao, recall e F1 de cada classe, sobre as predicoes agregadas."""
    y, p = df[f"{alvo}_real"], df[f"{alvo}_pred"]
    classes = sorted(set(y) | set(p))
    prec, rec, f1, sup = precision_recall_fscore_support(
        y, p, labels=classes, zero_division=0)
    return pd.DataFrame({
        "classe": classes, "precisao": prec, "recall": rec,
        "f1": f1, "suporte": sup,
    })


def resumo(df: pd.DataFrame, alvo: str) -> dict[str, float]:
    """Metricas de conjunto, sobre as predicoes agregadas."""
    y, p = df[f"{alvo}_real"], df[f"{alvo}_pred"]
    return {
        "acuracia": float((y == p).mean()),
        "acuracia_balanceada": float(balanced_accuracy_score(y, p)),
        "macro_f1": float(f1_score(y, p, average="macro", zero_division=0)),
        "mcc": float(matthews_corrcoef(y, p)),
        "kappa": float(cohen_kappa_score(y, p)),
    }


def barra(v: float, largura: int = 22) -> str:
    """Barra de texto para leitura rapida da dispersao entre folds."""
    return "#" * int(round(v * largura)) + "." * (largura - int(round(v * largura)))


def main() -> None:
    df = carregar()
    print(f"{len(df)} janelas · {df.fold.nunique()} folds · "
          f"protocolo leave-one-specimen-out\n")

    tudo_fold, tudo_classe, tudo_resumo = [], [], []

    for alvo, (titulo, papel) in ALVOS.items():
        print("=" * 74)
        print(f"{titulo}  —  {papel}")
        print("=" * 74)

        # ---- 1. resultados por fold, media e desvio ----------------------
        f = por_fold(df, alvo)
        media, dp = f.acuracia.mean(), f.acuracia.std(ddof=1)

        print("\n1. RESULTADOS POR FOLD")
        print(f"{'fold':>4} {'especime reservado':28s} {'n':>5} {'acuracia':>9}")
        for _, r in f.iterrows():
            print(f"{r.fold:>4} {r.especime_reservado:28s} {r.n_janelas:>5} "
                  f"{r.acuracia:>8.1%}  {barra(r.acuracia)}")
        print(f"\n     media +- desvio: {media:.1%} +- {dp:.1%}"
              f"   (min {f.acuracia.min():.1%}, max {f.acuracia.max():.1%})")

        # A dispersao e a informacao: um desvio grande diz que o desempenho
        # depende de qual montagem o modelo nunca viu, e nao e uma propriedade
        # estavel do modelo.
        if dp > 0.20:
            print("     desvio alto: o acerto depende fortemente do especime "
                  "reservado.")

        # ---- 2. matriz de confusao ---------------------------------------
        y, p = df[f"{alvo}_real"], df[f"{alvo}_pred"]
        classes = sorted(set(y) | set(p))
        cm = confusion_matrix(y, p, labels=classes)
        mc = pd.DataFrame(cm, index=[f"real {c}" for c in classes],
                          columns=[f"prev {c}" for c in classes])

        print("\n2. MATRIZ DE CONFUSAO  (linha = real, coluna = previsto)")
        print(mc.to_string())

        # ---- 3. precisao / recall / F1 por classe ------------------------
        pc = por_classe(df, alvo)
        print("\n3. POR CLASSE")
        print(f"{'classe':16s} {'precisao':>9} {'recall':>8} {'f1':>8} {'suporte':>8}")
        for _, r in pc.iterrows():
            print(f"{r.classe:16s} {r.precisao:>8.1%} {r.recall:>7.1%} "
                  f"{r.f1:>7.1%} {int(r.suporte):>8}")

        # ---- 4 e 5. macro-F1 e MCC ---------------------------------------
        s = resumo(df, alvo)
        print("\n4-5. METRICAS DE CONJUNTO")
        print(f"  acuracia              {s['acuracia']:.1%}   infla com a classe majoritaria")
        print(f"  acuracia balanceada   {s['acuracia_balanceada']:.1%}   cada classe pesa igual")
        print(f"  macro-F1              {s['macro_f1']:.3f}   media dos F1, sem peso por suporte")
        print(f"  MCC                   {s['mcc']:.3f}   alto so quando TODAS as classes vao bem")
        print(f"  kappa de Cohen        {s['kappa']:.3f}   corrige o acerto ao acaso")

        # Onde acuracia e MCC divergem, a divergencia e o achado.
        if s["acuracia"] - s["acuracia_balanceada"] > 0.05:
            print(f"\n  A acuracia esta {s['acuracia'] - s['acuracia_balanceada']:.1%} "
                  f"acima da balanceada: o desempenho e desigual entre classes,")
            print("  e o numero simples favorece as mais frequentes.")

        print()

        f.insert(0, "alvo", alvo); tudo_fold.append(f)
        pc.insert(0, "alvo", alvo); tudo_classe.append(pc)
        tudo_resumo.append({"alvo": alvo, **s,
                            "acuracia_media_folds": media, "desvio_folds": dp})
        mc.to_csv(DATA_INTERIM / f"metricas_confusao_{alvo}.csv")

    pd.concat(tudo_fold).to_csv(DATA_INTERIM / "metricas_por_fold.csv", index=False)
    pd.concat(tudo_classe).to_csv(DATA_INTERIM / "metricas_por_classe.csv", index=False)
    pd.DataFrame(tudo_resumo).to_csv(DATA_INTERIM / "metricas_resumo.csv", index=False)

    print("=" * 74)
    print("salvos em", DATA_INTERIM)
    for n in ["metricas_por_fold", "metricas_por_classe", "metricas_resumo",
              "metricas_confusao_fault_type", "metricas_confusao_severity"]:
        print(f"  {n}.csv")


if __name__ == "__main__":
    main()
