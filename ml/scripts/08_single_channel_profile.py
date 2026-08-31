"""Perfil de instrumentacao de canal unico.

Motivacao: o dataset KAIST tem 4 acelerometros e 3 fases de corrente, mas um
sensor industrial tipico de monitoramento fornece UM canal de vibracao e nenhuma
corrente. O modelo do TCC (metodologia e resultados) continua sendo o do KAIST
completo; este script mede o que resta quando so ha um canal, para dimensionar
honestamente o modo de campo do software.

Diferenca em relacao a 03_extract_features.py: os indicadores normativos sao
calculados A PARTIR DO CANAL UNICO, e nao do maior valor entre os quatro — que
seria informacao indisponivel na instrumentacao real.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_INTERIM, MS2_TO_G  # noqa: E402
from kaist.features import spectral, time_domain  # noqa: E402
from kaist.loaders import discover_sessions, load_vibration  # noqa: E402
from kaist.severity import normative_indicators  # noqa: E402

WINDOW_SECONDS = 1.0
CHANNEL = 0        # acc1: acelerometro radial do mancal proximo ao rotor


def extract(sf, channel: int = CHANNEL) -> list[dict]:
    vib, fs = load_vibration(sf.vibration_path)
    n = int(fs * WINDOW_SECONDS)
    meta = sf.meta.as_dict()

    rows = []
    for w in range(int(vib.shape[0] / n)):
        bloco = vib[w * n:(w + 1) * n, channel:channel + 1]   # (n, 1) em m/s^2
        bloco_g = bloco[:, 0] * MS2_TO_G

        row = dict(meta)
        row["window_index"] = w
        for k, v in time_domain(bloco_g).items():
            row[f"vib_{k}"] = v

        hann = np.hanning(n)
        amp = np.abs(np.fft.rfft(bloco_g * hann)) * (2.0 / hann.sum())
        freqs = np.fft.rfftfreq(n, d=1.0 / fs)
        for k, v in spectral(amp, freqs).items():
            row[f"vib_{k}"] = v

        # indicadores normativos do canal unico
        row.update(normative_indicators(bloco, fs))
        rows.append(row)
    return rows


def main() -> None:
    sessions = discover_sessions()
    todas = []
    for i, (sid, sf) in enumerate(sessions.items(), 1):
        linhas = extract(sf)
        todas.extend(linhas)
        print(f"[{i:2d}/{len(sessions)}] {sid:22s} {len(linhas):4d} janelas", flush=True)

    df = pd.DataFrame(todas)
    out = DATA_INTERIM / "features_single_channel.parquet"
    df.to_parquet(out, index=False)
    print(f"\n{df.shape[0]} janelas x {df.shape[1]} colunas -> {out}")

    feats = [c for c in df.columns if c.startswith(("vib_", "iso_"))]
    print(f"features do perfil de canal unico: {len(feats)}")


if __name__ == "__main__":
    main()
