"""A janela de 1 s cabe no que o coletor de campo consegue adquirir?

O conflito
----------
O AMS 2140 limita medicoes de quatro canais a 6.400 linhas (p.122 do manual);
apenas o canal unico chega a 12.800. Num analisador FFT a duracao da aquisicao
e `T = linhas / Fmax`, entao:

    1 canal,  12.800 linhas, Fmax 10 kHz -> 1,28 s @ 25.600 Hz   cabe em 1,0 s
    4 canais,  6.400 linhas, Fmax 10 kHz -> 0,64 s @ 25.600 Hz   NAO cabe

Baixar o Fmax para 6,4 kHz devolveria 1,0 s, mas a 16.384 Hz — outra taxa de
amostragem, e sem a banda de 8 a 12,8 kHz que alimenta `band_vhi`. Trocar a
taxa de amostragem entre treino e campo e o tipo de divergencia que nao gera
erro, so diagnostico errado.

A alternativa e treinar com janela mais curta. Isso custa resolucao espectral:
a 1,0 s cada bin vale 1 Hz; a 0,5 s, 2 Hz — e a meia-largura das bandas de
harmonico (`HARMONIC_HALF_WIDTH`) e 1,5 Hz, ou seja, passa a valer menos de um
bin. A pergunta e quanto disso o modelo sente.

Este script mede, para o perfil de vibracao pura (4 acelerometros, sem
corrente), a acuracia na identificacao do tipo com janelas de 1,0 s e 0,5 s,
sob leave-one-specimen-out.
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
from kaist.features import vibration_features  # noqa: E402
from kaist.loaders import discover_sessions, load_vibration  # noqa: E402
from kaist.splits import leave_one_specimen_out  # noqa: E402

JANELAS_S = (1.0, 0.5)
MAX_SEGUNDOS = 60.0     # todas as sessoes de falha tem 60 s
SEED = 42


def extrair(janela_s: float) -> pd.DataFrame:
    """Features de vibracao pura (4 canais + indicadores ISO) para uma janela."""
    linhas = []
    for sid, sf in sorted(discover_sessions().items()):
        if sf.vibration_path is None:
            continue

        vib, fs = load_vibration(sf.vibration_path)
        vib = vib[: int(fs * MAX_SEGUNDOS), :4]
        n = int(fs * janela_s)

        for w in range(len(vib) // n):
            f = vibration_features(vib[w * n:(w + 1) * n], fs)
            f["session_id"] = sid
            f["fam"] = sf.meta.fault_family
            f["load_nm"] = float(sf.meta.load_nm)
            linhas.append(f)

    return pd.DataFrame(linhas)


def avaliar(df: pd.DataFrame) -> tuple[float, dict[str, float], int]:
    """Acuracia out-of-fold e recall por familia, sob leave-one-specimen-out."""
    colunas = [c for c in df.columns
               if c.startswith(("vib_", "iso_")) or c == "load_nm"]
    labels = sorted(df.fam.unique())
    y = df.fam.map({c: i for i, c in enumerate(labels)}).to_numpy()
    X = df[colunas].to_numpy(dtype=np.float32)
    pred = np.full(len(df), -1)

    for f in leave_one_specimen_out(discover_sessions()):
        tr = df.session_id.isin(f.train_sessions).to_numpy()
        te = df.session_id.isin(f.test_sessions).to_numpy()
        if not te.any():
            continue

        rf = RandomForestClassifier(
            n_estimators=400, max_depth=12, min_samples_leaf=3,
            class_weight="balanced", n_jobs=-1, random_state=SEED).fit(X[tr], y[tr])
        xgb = XGBClassifier(
            n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8,
            colsample_bytree=0.8, tree_method="hist", n_jobs=-1, random_state=SEED)
        xgb.fit(X[tr], y[tr], sample_weight=compute_sample_weight("balanced", y[tr]))
        pred[te] = ((rf.predict_proba(X[te]) + xgb.predict_proba(X[te])) / 2).argmax(1)

    recall = {fam: float((pred[y == i] == i).mean()) for i, fam in enumerate(labels)}
    return float((pred == y).mean()), recall, len(colunas)


def main() -> None:
    resultados = {}
    for janela in JANELAS_S:
        cache = DATA_INTERIM / f"vib_only_{janela:.1f}s.parquet".replace(".", "_", 1)
        if cache.exists():
            df = pd.read_parquet(cache)
            print(f"janela {janela:.1f}s: cache ({len(df)} janelas)")
        else:
            print(f"janela {janela:.1f}s: extraindo...")
            df = extrair(janela)
            df.to_parquet(cache, index=False)
            print(f"janela {janela:.1f}s: {len(df)} janelas extraidas")

        acc, recall, n_feat = avaliar(df)
        resultados[janela] = (acc, recall, n_feat, len(df))

    print("\n" + "=" * 70)
    print("VIBRACAO PURA (4 acelerometros, sem corrente) POR TAMANHO DE JANELA")
    print("=" * 70)
    print(f"{'janela':>8s} {'janelas':>9s} {'feats':>6s} {'acuracia':>10s}   recall por familia")
    for janela, (acc, recall, n_feat, n) in resultados.items():
        det = "  ".join(f"{k}={v:.0%}" for k, v in sorted(recall.items()))
        print(f"{janela:7.1f}s {n:9d} {n_feat:6d} {acc:10.1%}   {det}")

    a1, a05 = resultados[1.0][0], resultados[0.5][0]
    n1, n05 = resultados[1.0][3], resultados[0.5][3]

    print("\n" + "=" * 70)
    print(f"Diferenca: {a05 - a1:+.1%} ao encurtar de 1,0 s para 0,5 s.")
    if a05 > a1 + 0.02:
        print("A janela curta e MELHOR, nao pior. A perda de resolucao espectral")
        print(f"e mais que compensada pelo dobro de janelas de treino "
              f"({n1} -> {n05}): neste volume de dados o fator limitante e a")
        print("quantidade de exemplos, nao a resolucao em frequencia. O perfil")
        print("de quatro canais pode ser treinado a 0,5 s e cabe nos 0,64 s que")
        print("o coletor entrega com Fmax de 10 kHz.")
    elif abs(a05 - a1) <= 0.02:
        print("Encurtar a janela nao custa desempenho relevante: o perfil de")
        print("quatro canais pode ser treinado a 0,5 s e passa a caber nos")
        print("0,64 s que o coletor entrega com Fmax de 10 kHz.")
    else:
        print("A janela curta custa desempenho. Nesse caso vale coletar duas")
        print("aquisicoes seguidas do mesmo ponto em vez de encurtar a janela.")

    print()
    print("RESSALVA: os dois numeros sao comparaveis entre si (mesmo trecho de")
    print(f"{MAX_SEGUNDOS:.0f} s por sessao), mas NAO com os 88,7 % ja reportados,")
    print("que usam a duracao integral das sessoes. Ha menos dados de treino nos")
    print("dois casos aqui — e e por isso que dobrar as janelas ajuda tanto.")

    pd.DataFrame([
        {"janela_s": j, "acuracia_tipo": r[0], "n_features": r[2], "n_janelas": r[3]}
        for j, r in resultados.items()
    ]).to_csv(DATA_INTERIM / "janela_curta.csv", index=False)
    print(f"\nresumo salvo em {DATA_INTERIM / 'janela_curta.csv'}")


if __name__ == "__main__":
    main()
