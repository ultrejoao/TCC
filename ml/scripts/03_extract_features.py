"""Extrai a matriz de features de todas as 45 sessoes.

Janelamento de 1 s SEM sobreposicao. A ausencia de overlap e deliberada:
janelas sobrepostas compartilham amostras e aumentam a correlacao entre
vizinhas, o que infla o numero aparente de exemplos sem acrescentar informacao.

As duas modalidades tem taxas diferentes (25.600,00 Hz e 25.608,19 Hz), entao o
alinhamento e feito por TEMPO: a janela k cobre [k, k+1) segundos em ambas, com
indices calculados a partir da respectiva taxa.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import CURRENT_CHANNEL, DATA_INTERIM  # noqa: E402
from kaist.features import (  # noqa: E402
    current_features,
    temperature_metadata,
    vibration_features,
)
from kaist.loaders import discover_sessions, load_current_temp, load_vibration  # noqa: E402

WINDOW_SECONDS = 1.0


def extract_session(sid, sf) -> list[dict]:
    vib, fs_v = load_vibration(sf.vibration_path)
    ct, fs_c = load_current_temp(sf.tdms_path)
    cur = ct[CURRENT_CHANNEL]

    n_v = int(fs_v * WINDOW_SECONDS)
    n_c = int(fs_c * WINDOW_SECONDS)
    n_windows = min(int(vib.shape[0] / n_v), int(len(cur) / n_c))

    meta = sf.meta.as_dict()
    rows = []
    for w in range(n_windows):
        vb = vib[w * n_v:(w + 1) * n_v, :]
        cb = cur[w * n_c:(w + 1) * n_c]

        row = dict(meta)
        row["window_index"] = w
        row["window_start_s"] = w * WINDOW_SECONDS
        row.update(vibration_features(vb, fs_v))
        row.update(current_features(cb, fs_c))
        row.update(temperature_metadata(
            ct["temp1"][w * n_c:(w + 1) * n_c],
            ct["temp2"][w * n_c:(w + 1) * n_c],
        ))
        rows.append(row)
    return rows


def main() -> None:
    sessions = discover_sessions()
    all_rows: list[dict] = []

    for i, (sid, sf) in enumerate(sessions.items(), 1):
        rows = extract_session(sid, sf)
        all_rows.extend(rows)
        print(f"[{i:2d}/{len(sessions)}] {sid:22s} {sf.meta.label:8s} "
              f"{len(rows):4d} janelas  (acumulado {len(all_rows)})", flush=True)

    df = pd.DataFrame(all_rows)
    out = DATA_INTERIM / "features_1s.parquet"
    try:
        df.to_parquet(out, index=False)
    except ImportError:  # sem pyarrow/fastparquet: nao perder a extracao
        out = out.with_suffix(".csv")
        df.to_csv(out, index=False)
        print("AVISO: parquet indisponivel, salvo como CSV")

    print(f"\nmatriz final: {df.shape[0]} janelas x {df.shape[1]} colunas")
    print(f"salvo em {out}")
    print("\njanelas por classe:")
    print(df.label.value_counts().to_string())
    print("\nNaN/inf nas features:")
    num = df.select_dtypes(include=[np.number])
    print(f"  NaN: {int(num.isna().sum().sum())}  inf: {int(np.isinf(num.to_numpy()).sum())}")


if __name__ == "__main__":
    main()
