"""Indicadores normativos de vibracao (ISO 10816 / ISO 20816).

Papel no sistema: **camada de validacao fisica**, exibida ao lado da classe
prevista pelo modelo. Nao substitui a predicao — sinaliza divergencia entre o
diagnostico estatistico e o criterio normativo.

Quatro indicadores, cada um sensivel a uma familia de falha diferente:

    v_iso   velocidade RMS 10-1000 Hz  [mm/s]  severidade global (ISO 10816)
    v_1x    velocidade RMS na rotacao  [mm/s]  desbalanceamento
    v_2x    velocidade RMS em 2x       [mm/s]  desalinhamento
    a_hf    aceleracao RMS 1-10 kHz    [g]     impacto de rolamento

Por que a velocidade e nao a aceleracao: a ISO avalia severidade em velocidade,
grandeza proporcional a energia de vibracao na faixa de operacao de maquinas
rotativas. A conversao e feita no dominio da frequencia, V(f) = A(f)/(2*pi*f).

Limitacao documentada (ver docs/02-resultados-baseline.md, secao 7): em
magnitude absoluta (Criterio I da norma) todas as 45 sessoes do KAIST caem na
zona A, inclusive rolamentos com defeito de 3 mm — a bancada e pequena e rigida,
e a integracao para velocidade atenua a alta frequencia onde vive a falha de
rolamento. Os indicadores por isso sao mais informativos de forma RELATIVA, o
que corresponde ao Criterio II da propria norma (variacao sobre uma referencia
estabelecida).
"""

from __future__ import annotations

import numpy as np

from config import MS2_TO_G, ROTATION_HZ

# Banda de avaliacao da ISO 10816 para maquinas de 600 a 12.000 rpm.
ISO_BAND = (10.0, 1_000.0)
# Banda de impacto de rolamento (fora do escopo da ISO 10816).
HF_BAND = (1_000.0, 10_000.0)

HARMONIC_HALF_WIDTH = 1.5  # Hz

# ISO 10816-1: limites das zonas A/B, B/C e C/D em mm/s RMS.
ISO_ZONE_LIMITS = {
    "I": (0.71, 1.80, 4.50),    # maquinas pequenas, ate 15 kW
    "II": (1.12, 2.80, 7.10),   # maquinas medias, 15 a 75 kW
    "III": (1.80, 4.50, 11.2),  # maquinas grandes, fundacao rigida
    "IV": (2.80, 7.10, 18.0),   # maquinas grandes, fundacao flexivel
}

# Zona da norma -> classe de severidade do sistema.
ZONE_TO_LABEL = {"A": "HEALTHY", "B": "HEALTHY", "C": "WARNING", "D": "FAILURE"}

_EPS = 1e-12


def _velocity_rms_mms(amp: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Velocidade RMS [mm/s] na banda, integrando o espectro de aceleracao [m/s^2]."""
    sel = (freqs >= lo) & (freqs <= hi)
    if not sel.any():
        return np.zeros(amp.shape[1] if amp.ndim == 2 else 1)
    denom = (2.0 * np.pi * freqs[sel])
    denom = denom[:, None] if amp.ndim == 2 else denom
    v_peak = amp[sel] / (denom + _EPS)          # m/s, pico
    return np.sqrt(np.sum((v_peak / np.sqrt(2)) ** 2, axis=0)) * 1000.0


def _accel_rms_g(amp: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Aceleracao RMS [g] na banda."""
    sel = (freqs >= lo) & (freqs <= hi)
    if not sel.any():
        return np.zeros(amp.shape[1] if amp.ndim == 2 else 1)
    return np.sqrt(np.sum((amp[sel] / np.sqrt(2)) ** 2, axis=0)) * MS2_TO_G


def normative_indicators(block_ms2: np.ndarray, fs: float,
                         rot_hz: float = ROTATION_HZ) -> dict[str, float]:
    """Indicadores normativos de uma janela. `block_ms2` em m/s^2, shape (n, canais).

    Conforme a norma, adota-se o MAIOR valor entre os pontos de medicao.
    """
    n = block_ms2.shape[0]
    hann = np.hanning(n)
    window = hann[:, None] if block_ms2.ndim == 2 else hann
    amp = np.abs(np.fft.rfft(block_ms2 * window, axis=0)) * (2.0 / hann.sum())
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)

    h = HARMONIC_HALF_WIDTH
    return {
        "iso_v_rms_mms": float(_velocity_rms_mms(amp, freqs, *ISO_BAND).max()),
        "iso_v_1x_mms": float(_velocity_rms_mms(amp, freqs, rot_hz - h, rot_hz + h).max()),
        "iso_v_2x_mms": float(_velocity_rms_mms(amp, freqs, 2 * rot_hz - h, 2 * rot_hz + h).max()),
        "iso_a_hf_g": float(_accel_rms_g(amp, freqs, *HF_BAND).max()),
    }


def iso_zone(v_rms_mms: float, machine_class: str = "I") -> str:
    """Criterio I da ISO 10816: zona A/B/C/D pela magnitude absoluta."""
    ab, bc, cd = ISO_ZONE_LIMITS[machine_class]
    if v_rms_mms < ab:
        return "A"
    if v_rms_mms < bc:
        return "B"
    if v_rms_mms < cd:
        return "C"
    return "D"


def compare_to_baseline(current: dict[str, float],
                        baseline: dict[str, float] | None) -> dict[str, float] | None:
    """Criterio II da ISO: variacao sobre uma referencia estabelecida.

    `baseline` e a medicao que o tecnico marcou como referencia daquele motor.
    E OPCIONAL: quando ausente, retorna None e o sistema opera apenas com a
    predicao do modelo e os indicadores absolutos.

    Retorna a razao e a variacao percentual de cada indicador, o que permite
    comunicar o diagnostico de forma direta ao usuario — por exemplo,
    "a vibracao aumentou 180% em relacao a condicao normal conhecida".
    """
    if not baseline:
        return None

    out: dict[str, float] = {}
    for k, v in current.items():
        ref = baseline.get(k)
        if ref is None:
            continue
        ratio = v / (ref + _EPS)
        out[f"{k}_ratio"] = float(ratio)
        out[f"{k}_change_pct"] = float((ratio - 1.0) * 100.0)
    return out
