"""Inventario e sanidade fisica das 45 sessoes do KAIST.

"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_INTERIM, MS2_TO_G  # noqa: E402
from kaist.loaders import discover_sessions, load_current_temp, load_vibration  # noqa: E402


def dominant_freq(x: np.ndarray, fs: float, fmin: float, fmax: float) -> float:
    """Frequencia de maior energia na banda [fmin, fmax], via FFT de um trecho."""
    seg = x[: int(fs * 10)]                      # 10 s bastam p/ resolucao de 0.1 Hz
    seg = seg - seg.mean()
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), d=1.0 / fs)
    band = (freqs >= fmin) & (freqs <= fmax)
    return float(freqs[band][np.argmax(spec[band])])


def main() -> None:
    sessions = discover_sessions()
    print(f"{len(sessions)} sessoes descobertas\n")

    rows = []
    for i, (sid, sf) in enumerate(sessions.items(), 1):
        row = sf.meta.as_dict()
        row["has_vibration"] = sf.vibration_path is not None
        row["has_current_temp"] = sf.tdms_path is not None

        if sf.vibration_path:
            vib, fs_v = load_vibration(sf.vibration_path)
            row["fs_vib"] = fs_v
            row["n_vib"] = vib.shape[0]
            row["dur_vib_s"] = round(vib.shape[0] / fs_v, 2)
            row["vib_nan"] = int(np.isnan(vib).sum())
            for c in range(vib.shape[1]):
                ch = vib[:, c] * MS2_TO_G          # m/s^2 -> g
                row[f"acc{c+1}_rms_g"] = round(float(np.sqrt((ch**2).mean())), 4)
                row[f"acc{c+1}_mean_g"] = round(float(ch.mean()), 6)
                row[f"acc{c+1}_kurt"] = round(
                    float(((ch - ch.mean()) ** 4).mean() / (ch.std() ** 4)), 3
                )
            row["rot_freq_hz"] = round(dominant_freq(vib[:, 0], fs_v, 5, 120), 2)
            del vib

        if sf.tdms_path:
            ct, fs_c = load_current_temp(sf.tdms_path)
            row["fs_ct"] = round(fs_c, 2)
            row["n_ct"] = len(ct["temp1"])
            row["dur_ct_s"] = round(len(ct["temp1"]) / fs_c, 2)
            row["ct_nan"] = int(sum(np.isnan(v).sum() for v in ct.values()))
            for name in ("temp1", "temp2"):
                row[f"{name}_mean_c"] = round(float(ct[name].mean()), 2)
                row[f"{name}_max_c"] = round(float(ct[name].max()), 2)
            for name in ("current_r", "current_s", "current_t"):
                row[f"{name}_rms_a"] = round(float(np.sqrt((ct[name] ** 2).mean())), 4)
            row["line_freq_hz"] = round(dominant_freq(ct["current_r"], fs_c, 20, 120), 2)
            del ct

        rows.append(row)
        print(
            f"[{i:2d}/45] {sid:22s} {row['label']:8s} "
            f"vib={row.get('dur_vib_s','--')}s ct={row.get('dur_ct_s','--')}s "
            f"acc1={row.get('acc1_rms_g','--')}g Irms={row.get('current_r_rms_a','--')}A "
            f"T={row.get('temp1_mean_c','--')}C rot={row.get('rot_freq_hz','--')}Hz",
            flush=True,
        )

    df = pd.DataFrame(rows)
    out = DATA_INTERIM / "session_inventory.csv"
    df.to_csv(out, index=False)
    print(f"\ninventario salvo em {out}")


if __name__ == "__main__":
    main()
