"""Schemas da forma de onda para exibicao."""

from pydantic import BaseModel


class WaveformPoint(BaseModel):
    """Um balde de amostras reduzido a min e max.

    Envelope, e nao uma amostra representativa: em vibracao o conteudo
    diagnostico esta nos picos curtos, que a decimacao simples descartaria.
    """

    t: float
    min: float
    max: float


class WaveformOut(BaseModel):
    measurement_id: str
    channel: int
    channel_name: str
    unit: str

    sample_rate_hz: float
    n_samples: int
    duration_s: float
    decimation: int
    points: list[WaveformPoint]

    # calculados sobre o sinal inteiro, nao sobre os pontos exibidos
    peak_to_peak_g: float
    peak_g: float
    rms_g: float
    crest_factor: float
