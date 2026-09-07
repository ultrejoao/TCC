"""Extracao de features por perfil de instrumentacao.

O mesmo codigo roda no treino (sobre o dataset KAIST) e em producao (sobre o
arquivo que o tecnico envia). Se divergissem, o modelo receberia em campo
features calculadas de forma diferente das do treino — um erro silencioso e
dificil de detectar.

Perfis
------
`kaist_full`    4 acelerometros + 1 fase de corrente -> 97 features
                Usado na metodologia e nos resultados do TCC.

`field_single`  1 canal de vibracao -> 25 features
                Usado com instrumentacao de campo, que tipicamente fornece um
                unico ponto de medicao e nenhuma corrente.

A diferenca medida entre os perfis (leave-one-specimen-out):

                    tipo de falha   severidade
    kaist_full          88,7 %         63,1 %
    field_single        85,4 %         56,1 %

Medido e NAO implementado: quatro acelerometros sem corrente chegam a 89,5 %
com janela de 0,5 s (ml/scripts/14_janela_curta.py). A corrente nao contribui
para a identificacao do tipo — o que separa os perfis e o numero de canais de
vibracao. Fica registrado como trabalho futuro, dependente de instrumentacao
com mais de um sensor.

O diagnostico de TIPO e robusto a reducao de instrumentacao (rolamento segue em
100 %); a severidade e o reconhecimento da condicao normal e que dependem da
instrumentacao completa.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MS2_TO_G, ROTATION_HZ  # noqa: E402
from kaist.features import current_features, spectral, time_domain  # noqa: E402
from kaist.severity import normative_indicators  # noqa: E402
from signals.readers import RawSignal  # noqa: E402

PROFILE_FULL = "kaist_full"
PROFILE_SINGLE = "field_single"


@dataclass(frozen=True)
class ProfileSpec:
    """Requisitos de entrada de um perfil."""

    name: str
    min_vibration_channels: int
    requires_current: bool
    description: str


PROFILES: dict[str, ProfileSpec] = {
    PROFILE_FULL: ProfileSpec(
        PROFILE_FULL, 4, True,
        "4 acelerometros e uma fase de corrente (bancada instrumentada)"),
    PROFILE_SINGLE: ProfileSpec(
        PROFILE_SINGLE, 1, False,
        "um canal de vibracao (instrumentacao de campo)"),
}


def select_profile(n_vibration_channels: int, has_current: bool) -> str:
    """Escolhe o perfil mais completo compativel com o que foi enviado.

    Um arquivo de quatro canais sem corrente cai no perfil de um canal. Um
    perfil dedicado de quatro canais foi medido (89,5 %, ver
    ml/scripts/14_janela_curta.py) e nao foi treinado: a instrumentacao em uso
    tem um sensor so, e um perfil sem artefato desviaria a inferencia para um
    modelo inexistente.
    """
    if n_vibration_channels >= 4 and has_current:
        return PROFILE_FULL
    if n_vibration_channels >= 1:
        return PROFILE_SINGLE
    raise ValueError("nenhum canal de vibracao disponivel")


def _window_count(n_samples: int, fs: float, window_seconds: float) -> int:
    return int(n_samples / int(fs * window_seconds))


def single_channel_features(block_ms2: np.ndarray, fs: float,
                            rot_hz: float = ROTATION_HZ) -> dict[str, float]:
    """Features do perfil `field_single`, a partir de UM canal.

    `block_ms2` tem shape (n,) ou (n, 1), em m/s^2. `rot_hz` posiciona as
    bandas de 1x, 2x e 3x a rotacao.
    """
    coluna = block_ms2.reshape(-1, 1)
    sinal_g = coluna[:, 0] * MS2_TO_G

    out: dict[str, float] = {}
    for k, v in time_domain(sinal_g).items():
        out[f"vib_{k}"] = v

    n = len(sinal_g)
    hann = np.hanning(n)
    amp = np.abs(np.fft.rfft(sinal_g * hann)) * (2.0 / hann.sum())
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    for k, v in spectral(amp, freqs, rot_hz).items():
        out[f"vib_{k}"] = v

    # indicadores normativos calculados do proprio canal
    out.update(normative_indicators(coluna, fs, rot_hz))
    return out


def full_features(block_ms2: np.ndarray, fs_vib: float,
                  current_block: np.ndarray | None, fs_cur: float | None,
                  channel_names: list[str] | None = None,
                  rot_hz: float = ROTATION_HZ) -> dict[str, float]:
    """Features do perfil `kaist_full`: 4 acelerometros + uma fase de corrente."""
    from kaist.features import vibration_features

    out = vibration_features(block_ms2, fs_vib, rot_hz)
    if current_block is not None and fs_cur:
        out.update(current_features(current_block, fs_cur))
    return out


def extract_windows(signal: RawSignal, profile: str, window_seconds: float = 1.0,
                    channel: int = 0, current: RawSignal | None = None,
                    load_nm: float | None = None,
                    rot_hz: float = ROTATION_HZ) -> list[dict[str, float]]:
    """Extrai as features de todas as janelas de um sinal.

    Retorna uma lista de dicionarios, um por janela. O chamador decide como
    agregar as janelas numa unica predicao (ver `aggregate_windows`).

    `rot_hz` e a rotacao do eixo medido. O padrao reproduz a bancada KAIST, de
    modo que o treino permanece identico; em campo o valor deve vir do motor.
    """
    if profile not in PROFILES:
        raise ValueError(f"perfil desconhecido: {profile}")

    fs = signal.sample_rate
    n = int(fs * window_seconds)
    if signal.n_samples < n:
        raise ValueError(
            f"sinal curto demais: {signal.duration_s:.2f}s, "
            f"minimo {window_seconds}s para uma janela")

    janelas: list[dict[str, float]] = []
    total = _window_count(signal.n_samples, fs, window_seconds)

    for w in range(total):
        fatia = slice(w * n, (w + 1) * n)
        if profile == PROFILE_SINGLE:
            linha = single_channel_features(signal.samples[fatia, channel], fs, rot_hz)
        else:
            bloco_cur, fs_cur = None, None
            if current is not None:
                nc = int(current.sample_rate * window_seconds)
                bloco_cur = current.samples[w * nc:(w + 1) * nc, 0]
                fs_cur = current.sample_rate
            linha = full_features(signal.samples[fatia, :4], fs, bloco_cur, fs_cur,
                                  rot_hz=rot_hz)

        if load_nm is not None:
            linha["load_nm"] = float(load_nm)
        janelas.append(linha)

    return janelas


def aggregate_windows(janelas: list[dict[str, float]]) -> dict[str, float]:
    """Resume as janelas de uma medicao numa unica linha de features.

    Usa a MEDIANA, nao a media: uma janela contaminada por impacto pontual
    (batida, ajuste do sensor durante a coleta) desloca a media e nao a mediana.
    """
    if not janelas:
        raise ValueError("nenhuma janela extraida")
    chaves = janelas[0].keys()
    return {k: float(np.median([j[k] for j in janelas])) for k in chaves}
