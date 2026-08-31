"""Adaptadores de leitura de sinal.

Cada instrumento grava num formato proprio. Em vez de espalhar essa variacao
pelo pipeline, todo formato e normalizado aqui num `RawSignal`, e o restante do
sistema so conhece essa estrutura.

Consequencia pratica: dar suporte a um instrumento novo e escrever UM adaptador
e registra-lo. Nem a extracao de features, nem o modelo, nem a API mudam.

Formatos suportados hoje:

    .mat    LMS Test.Lab (formato do dataset KAIST) — taxa embutida
    .tdms   National Instruments FlexLogger         — taxa embutida
    .wav    audio/vibracao PCM                      — taxa embutida
    .npy    array NumPy cru                         — taxa deve ser informada
    .csv    texto delimitado                        — taxa deve ser informada

Formatos autodescritivos trazem a taxa de amostragem no proprio arquivo. Os
demais exigem que o tecnico informe `sample_rate_hz` no formulario — sem ela
nao ha como calcular frequencia nenhuma, e adivinhar seria pior que recusar.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

G_TO_MS2 = 9.80665


class SignalReadError(ValueError):
    """Falha ao interpretar o arquivo de sinal."""


@dataclass
class RawSignal:
    """Sinal normalizado, independente do instrumento de origem.

    `samples` tem shape (n_amostras, n_canais) e esta SEMPRE em m/s^2, porque e
    a unidade que a extracao de features e os indicadores normativos esperam.
    """

    samples: np.ndarray
    sample_rate: float
    channel_names: list[str]
    source_format: str
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.samples.ndim == 1:
            self.samples = self.samples[:, None]
        if self.samples.ndim != 2:
            raise SignalReadError(
                f"esperado sinal 2D (amostras, canais), obtido {self.samples.shape}")
        if self.sample_rate <= 0:
            raise SignalReadError(f"taxa de amostragem invalida: {self.sample_rate}")
        if len(self.channel_names) != self.samples.shape[1]:
            self.channel_names = [f"ch{i+1}" for i in range(self.samples.shape[1])]

    @property
    def n_samples(self) -> int:
        return int(self.samples.shape[0])

    @property
    def n_channels(self) -> int:
        return int(self.samples.shape[1])

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.sample_rate

    def channel(self, index: int) -> np.ndarray:
        return self.samples[:, index]


@runtime_checkable
class SignalReader(Protocol):
    suffixes: tuple[str, ...]

    def read(self, path: Path, **hints) -> RawSignal: ...


# ---------------------------------------------------------------------------
# formatos autodescritivos
# ---------------------------------------------------------------------------
class KaistMatReader:
    """`.mat` do LMS Test.Lab, formato do dataset KAIST.

    A estrutura `Signal` traz x_values.increment (o inverso da taxa) e
    y_values.values com as amostras em MKS (m/s^2).
    """

    suffixes = (".mat",)

    def read(self, path: Path, **hints) -> RawSignal:
        from scipy.io import loadmat

        mat = loadmat(path, struct_as_record=False, squeeze_me=True)
        if "Signal" not in mat:
            raise SignalReadError(
                f"{path.name}: .mat sem a estrutura 'Signal' esperada do Test.Lab")

        sig = mat["Signal"]
        values = np.asarray(sig.y_values.values, dtype=np.float64)
        fs = 1.0 / float(sig.x_values.increment)
        n_ch = values.shape[1] if values.ndim == 2 else 1
        return RawSignal(
            samples=values, sample_rate=fs,
            channel_names=[f"acc{i+1}" for i in range(n_ch)],
            source_format="lms_testlab_mat",
            metadata={"unit": "m/s^2"})


class TdmsReader:
    """`.tdms` do NI FlexLogger. Mantem apenas canais de aceleracao."""

    suffixes = (".tdms",)
    ACCEL_UNITS = {"m/s^2", "m/s2", "g"}

    def read(self, path: Path, **hints) -> RawSignal:
        from nptdms import TdmsFile

        canais: list[np.ndarray] = []
        nomes: list[str] = []
        fs: float | None = None

        with TdmsFile.open(path) as tf:
            for group in tf.groups():
                for ch in group.channels():
                    if len(ch) == 0:
                        continue                    # canal vazio: ignorar
                    unidade = (ch.properties.get("unit_string") or "").strip()
                    if unidade and unidade.lower() not in self.ACCEL_UNITS:
                        continue                    # temperatura, corrente etc.
                    dados = np.asarray(ch[:], dtype=np.float64)
                    if unidade.lower() == "g":
                        dados = dados * G_TO_MS2
                    canais.append(dados)
                    nomes.append(ch.name.split("/")[-1])
                    if fs is None and "wf_increment" in ch.properties:
                        fs = 1.0 / float(ch.properties["wf_increment"])

        if not canais:
            raise SignalReadError(f"{path.name}: nenhum canal de aceleracao encontrado")
        if fs is None:
            fs = _hint_sample_rate(hints, path)

        menor = min(len(c) for c in canais)
        return RawSignal(
            samples=np.column_stack([c[:menor] for c in canais]),
            sample_rate=fs, channel_names=nomes,
            source_format="ni_tdms", metadata={"unit": "m/s^2"})


class WavReader:
    """`.wav` PCM. Traz a taxa embutida; a escala e arbitraria."""

    suffixes = (".wav",)

    def read(self, path: Path, **hints) -> RawSignal:
        from scipy.io import wavfile

        fs, dados = wavfile.read(path)
        dados = np.asarray(dados, dtype=np.float64)

        # PCM inteiro vem em escala do formato; normaliza para [-1, 1] antes de
        # aplicar a sensibilidade informada
        if np.issubdtype(np.asarray(wavfile.read(path)[1]).dtype, np.integer):
            max_abs = float(np.iinfo(np.int32).max) if dados.max() > 32767 else 32768.0
            dados = dados / max_abs

        escala = float(hints.get("full_scale_ms2") or 1.0)
        return RawSignal(
            samples=dados * escala, sample_rate=float(fs),
            channel_names=[], source_format="wav",
            metadata={"unit": "m/s^2", "full_scale_ms2": escala})


# ---------------------------------------------------------------------------
# formatos que exigem a taxa informada
# ---------------------------------------------------------------------------
def _hint_sample_rate(hints: dict, path: Path) -> float:
    fs = hints.get("sample_rate_hz")
    if not fs:
        raise SignalReadError(
            f"{path.name}: o formato nao informa a taxa de amostragem. "
            f"Informe 'sample_rate_hz' junto com o arquivo.")
    fs = float(fs)
    if fs <= 0:
        raise SignalReadError(f"taxa de amostragem invalida: {fs}")
    return fs


def _to_ms2(dados: np.ndarray, hints: dict) -> np.ndarray:
    """Converte para m/s^2 conforme a unidade declarada pelo tecnico."""
    unidade = str(hints.get("unit", "m/s^2")).strip().lower()
    if unidade in {"g", "gs"}:
        return dados * G_TO_MS2
    if unidade in {"mm/s^2", "mm/s2"}:
        return dados / 1000.0
    return dados


class NpyReader:
    suffixes = (".npy",)

    def read(self, path: Path, **hints) -> RawSignal:
        dados = np.load(path).astype(np.float64)
        return RawSignal(
            samples=_to_ms2(dados, hints), sample_rate=_hint_sample_rate(hints, path),
            channel_names=[], source_format="npy", metadata={"unit": "m/s^2"})


class CsvReader:
    """CSV/TXT delimitado, com ou sem cabecalho.

    O delimitador e detectado automaticamente. Colunas nao numericas (tempo em
    texto, indices) sao descartadas.
    """

    suffixes = (".csv", ".txt", ".tsv")

    def read(self, path: Path, **hints) -> RawSignal:
        texto = path.read_text(encoding="utf-8", errors="replace")
        amostra = texto[:8192]
        try:
            dialect = csv.Sniffer().sniff(amostra, delimiters=",;\t| ")
            delim = dialect.delimiter
        except csv.Error:
            delim = ","

        linhas = [ln for ln in texto.splitlines() if ln.strip()]
        if not linhas:
            raise SignalReadError(f"{path.name}: arquivo vazio")

        nomes: list[str] = []
        primeira = [c.strip() for c in linhas[0].split(delim)]
        if not _todos_numericos(primeira):
            nomes = primeira
            linhas = linhas[1:]

        try:
            dados = np.array(
                [[float(c.replace(",", ".")) for c in ln.split(delim) if c.strip() != ""]
                 for ln in linhas], dtype=np.float64)
        except ValueError as exc:
            raise SignalReadError(
                f"{path.name}: linha com valor nao numerico ({exc})") from exc

        if dados.ndim == 1:
            dados = dados[:, None]

        return RawSignal(
            samples=_to_ms2(dados, hints), sample_rate=_hint_sample_rate(hints, path),
            channel_names=nomes, source_format="csv",
            metadata={"unit": "m/s^2", "delimiter": delim})


def _todos_numericos(campos: list[str]) -> bool:
    for c in campos:
        try:
            float(c.replace(",", "."))
        except ValueError:
            return False
    return bool(campos)


# ---------------------------------------------------------------------------
# registro
# ---------------------------------------------------------------------------
READERS: list[SignalReader] = [
    KaistMatReader(), TdmsReader(), WavReader(), NpyReader(), CsvReader(),
]


def supported_suffixes() -> set[str]:
    return {s for r in READERS for s in r.suffixes}


def read_signal(path: str | Path, **hints) -> RawSignal:
    """Le um arquivo de sinal, escolhendo o adaptador pela extensao.

    `hints` carrega o que o formato nao informa: `sample_rate_hz`, `unit`,
    `full_scale_ms2`.
    """
    path = Path(path)
    if not path.exists():
        raise SignalReadError(f"arquivo nao encontrado: {path}")

    sufixo = path.suffix.lower()
    for reader in READERS:
        if sufixo in reader.suffixes:
            return reader.read(path, **hints)

    raise SignalReadError(
        f"formato '{sufixo}' nao suportado. "
        f"Suportados: {', '.join(sorted(supported_suffixes()))}")
