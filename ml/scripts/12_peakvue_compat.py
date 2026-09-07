"""O que sobrevive quando a coleta e PeakVue em vez de forma de onda bruta.

Motivacao (levantamento de campo, 01/09/2026)
---------------------------------------------
Um tecnico que opera o Emerson CSI 2140 em rota industrial forneceu a
configuracao real de um ponto de rolamento:

    Ponto     M2P - Motor Inboard Horz PeakVue
    Global    1,3541 g Pico   (referencia 0,8863 -> +52,8 %, condicao "Aviso")
    Filtro    PeakVue, 1000 Hz
    Banda     40,5 xRPM / 3200 linhas
    Onda      40,5 xRPM / 4096 pontos
    Armazena  tendencia, espectro, forma de onda

Isso corrige a suposicao do experimento anterior (`perfil de 4 canais`), que
assumia forma de onda BRUTA de aceleracao. Na rota real o que se coleta e
PeakVue: um envelope por retificacao e retencao de pico sobre o sinal filtrado
em alta frequencia. Nao e o sinal bruto, e por isso nao alimenta o modelo
treinado no KAIST sem que se meca o custo.

O que este script faz
---------------------
Aplica a cadeia PeakVue ao sinal do KAIST e reavalia a identificacao do tipo de
falha sob o mesmo protocolo leave-one-specimen-out, comparando:

    A) BRUTO      1 canal de aceleracao, 25.600 Hz  (perfil `field_single`)
    B) PEAKVUE    o mesmo canal apos filtro passa-alta de 1000 Hz,
                  retificacao e retencao de pico reamostrada a 2.560 Hz

A hipotese fisica e que o PeakVue preserve o rolamento (foi projetado para
isso) e destrua desbalanceamento e desalinhamento, cuja assinatura vive em 1x e
2x a rotacao — abaixo do corte do filtro. Se confirmada, a consequencia pratica
e que os pontos PeakVue da rota nao substituem os pontos de baixa frequencia.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_INTERIM, MS2_TO_G  # noqa: E402
from kaist.features import spectral, time_domain  # noqa: E402
from kaist.loaders import discover_sessions, load_vibration  # noqa: E402
from kaist.splits import leave_one_specimen_out  # noqa: E402

CANAL = 0                 # acc1: radial no mancal, o ponto que a rota mediria
HP_CUTOFF = 1000.0        # Hz — filtro PeakVue lido do coletor
FS_PEAKVUE = 2560.0       # Hz — 2,56 x fmax de 1000 Hz
JANELA_S = 1.0
MAX_SEGUNDOS = 60.0       # todas as sessoes de falha tem 60 s; limita o custo
SEED = 42


def peakvue(sinal_g: np.ndarray, fs_in: float,
            hp: float = HP_CUTOFF, fs_out: float = FS_PEAKVUE) -> np.ndarray:
    """Emula a cadeia PeakVue da Emerson sobre um canal de aceleracao.

    Tres etapas, na ordem em que o coletor as aplica:

      1. passa-alta em `hp` — descarta a faixa de baixa frequencia, onde vivem
         1x e 2x a rotacao. E o que torna o PeakVue cego a desbalanceamento;
      2. retificacao (valor absoluto);
      3. retencao de pico: o maximo de cada bloco vira uma amostra da saida.
         Difere de decimacao comum, que descartaria justamente o impacto curto
         que caracteriza o defeito de pista.
    """
    sos = butter(4, hp, btype="highpass", fs=fs_in, output="sos")
    filtrado = np.abs(sosfiltfilt(sos, sinal_g))

    fator = int(round(fs_in / fs_out))
    n = (len(filtrado) // fator) * fator
    return filtrado[:n].reshape(-1, fator).max(axis=1)


def features_canal(x_g: np.ndarray, fs: float, prefixo: str) -> dict[str, float]:
    """Descritores de tempo e frequencia de um canal, com prefixo de origem."""
    out = {f"{prefixo}_{k}": v for k, v in time_domain(x_g).items()}

    hann = np.hanning(len(x_g))
    amp = np.abs(np.fft.rfft(x_g * hann)) * (2.0 / hann.sum())
    freqs = np.fft.rfftfreq(len(x_g), d=1.0 / fs)
    out.update({f"{prefixo}_{k}": v for k, v in spectral(amp, freqs).items()})
    return out


def extrair() -> pd.DataFrame:
    """Percorre as sessoes e devolve, por janela, as features das duas cadeias."""
    sessions = discover_sessions()
    linhas: list[dict] = []

    for i, (sid, sf) in enumerate(sorted(sessions.items()), 1):
        if sf.vibration_path is None:
            continue

        vib, fs = load_vibration(sf.vibration_path)
        sinal = vib[: int(fs * MAX_SEGUNDOS), CANAL] * MS2_TO_G

        n_bruto = int(fs * JANELA_S)
        n_pv = int(FS_PEAKVUE * JANELA_S)
        janelas = len(sinal) // n_bruto

        env = peakvue(sinal, fs)

        for w in range(janelas):
            bruto = sinal[w * n_bruto:(w + 1) * n_bruto]
            envelope = env[w * n_pv:(w + 1) * n_pv]
            if len(envelope) < n_pv:
                break

            linha = {"session_id": sid, "fam": sf.meta.fault_family}
            linha.update(features_canal(bruto, fs, "raw"))
            linha.update(features_canal(envelope, FS_PEAKVUE, "pv"))
            linhas.append(linha)

        print(f"  [{i:2d}/{len(sessions)}] {sid:22s} {janelas:3d} janelas")

    return pd.DataFrame(linhas)


def avaliar(df: pd.DataFrame, colunas: list[str], y: np.ndarray, folds) -> np.ndarray:
    """Predicoes out-of-fold do ensemble sobre o conjunto de colunas dado."""
    X = df[colunas].to_numpy(dtype=np.float32)
    pred = np.full(len(df), -1)

    for f in folds:
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

    return pred


def main() -> None:
    cache = DATA_INTERIM / "peakvue_features.parquet"
    if cache.exists():
        print(f"features em cache: {cache}\n")
        df = pd.read_parquet(cache)
    else:
        print("extraindo features das duas cadeias (bruto e PeakVue)\n")
        df = extrair()
        df.to_parquet(cache, index=False)
        print(f"\nsalvo em {cache}\n")

    labels = sorted(df.fam.unique())
    y = df.fam.map({c: i for i, c in enumerate(labels)}).to_numpy()
    folds = leave_one_specimen_out(discover_sessions())

    col_raw = [c for c in df.columns if c.startswith("raw_")]
    col_pv = [c for c in df.columns if c.startswith("pv_")]

    print(f"{len(df)} janelas · {len(folds)} folds · "
          f"{len(col_raw)} features por cadeia\n")

    cadeias = {
        f"BRUTO   aceleracao, {int(25600)} Hz": (col_raw, avaliar(df, col_raw, y, folds)),
        f"PEAKVUE envelope HP {HP_CUTOFF:.0f} Hz, {FS_PEAKVUE:.0f} Hz": (
            col_pv, avaliar(df, col_pv, y, folds)),
    }

    print("=" * 70)
    print("IDENTIFICACAO DO TIPO DE FALHA, POR CADEIA DE AQUISICAO")
    print("=" * 70)
    for nome, (_, pred) in cadeias.items():
        print(f"  {nome:44s} {(pred == y).mean():6.1%}")

    print("\n" + "=" * 70)
    print("RECALL POR FAMILIA — onde cada cadeia enxerga")
    print("=" * 70)
    print(f"{'familia':16s} {'bruto':>10s} {'peakvue':>10s} {'delta':>10s}")
    for i, fam in enumerate(labels):
        m = y == i
        r_raw = (list(cadeias.values())[0][1][m] == i).mean()
        r_pv = (list(cadeias.values())[1][1][m] == i).mean()
        print(f"{fam:16s} {r_raw:10.1%} {r_pv:10.1%} {r_pv - r_raw:+10.1%}")

    print("\n" + "=" * 70)
    print("O QUE O FILTRO REMOVE — amplitude em 1x e 2x a rotacao (g)")
    print("=" * 70)
    comp = df.groupby("fam")[["raw_amp_1x", "pv_amp_1x",
                              "raw_amp_2x", "pv_amp_2x"]].median()
    print(comp.to_string(float_format=lambda v: f"{v:.5f}"))

    print("\n" + "=" * 70)
    print("MATRIZ DE CONFUSAO DO PEAKVUE")
    print("=" * 70)
    pred_pv = list(cadeias.values())[1][1]
    cm = confusion_matrix(y, pred_pv, labels=range(len(labels)))
    print(pd.DataFrame(cm, index=labels, columns=labels).to_string())

    resumo = pd.DataFrame({
        "cadeia": list(cadeias),
        "acuracia_tipo": [(p == y).mean() for _, p in cadeias.values()],
    })
    destino = DATA_INTERIM / "peakvue_vs_raw.csv"
    resumo.to_csv(destino, index=False)
    print(f"\nresumo salvo em {destino}")


if __name__ == "__main__":
    main()
