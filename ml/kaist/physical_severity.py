"""Severidade pelo criterio fisico da ISO 10816, nao prevista pelo modelo.

Correlacao de Spearman com o nivel do defeito, por familia:

    rolamento         +0,82
    desalinhamento    +0,92
    desbalanceamento  +0,89
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from kaist.severity import ISO_ZONE_LIMITS, iso_zone

HEALTHY = "HEALTHY"
WARNING = "WARNING"
FAILURE = "FAILURE"


class SeverityCriterion(StrEnum):
    ABSOLUTE = "ISO_10816_ZONA"          # criterio I
    RELATIVE = "ISO_10816_VARIACAO"      # criterio II

RELATIVE_WARNING = 1.5
RELATIVE_FAILURE = 4.0


@dataclass
class PhysicalSeverity:
    """Condicao vibratoria avaliada por criterio fisico."""

    severity: str
    criterion: SeverityCriterion
    iso_zone: str
    v_rms_mms: float
    machine_class: str

    ratio_to_baseline: float | None = None
    explanation: str = ""
    supporting: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "criterion": str(self.criterion),
            "iso_zone": self.iso_zone,
            "v_rms_mms": round(self.v_rms_mms, 4),
            "machine_class": self.machine_class,
            "ratio_to_baseline": (round(self.ratio_to_baseline, 3)
                                  if self.ratio_to_baseline is not None else None),
            "explanation": self.explanation,
            "supporting": {k: round(v, 4) for k, v in self.supporting.items()},
        }


#: Indicador que caracteriza cada tipo de falha. NAO define a severidade —
#: serve para explicar ao usuario onde a energia se manifesta, complementando
#: o diagnostico do modelo.
DOMINANT_INDICATOR = {
    "unbalance": ("iso_v_1x_mms", "componente 1x a rotacao"),
    "misalignment": ("iso_a_hf_g", "alta frequencia"),
    "bearing": ("iso_a_hf_g", "alta frequencia"),
    "normal": ("iso_v_rms_mms", "vibracao global"),
}


def evaluate(indicators: dict[str, float], *, machine_class: str = "I",
             baseline: dict[str, float] | None = None,
             fault_type: str | None = None) -> PhysicalSeverity:
    """Avalia a condicao vibratoria a partir dos indicadores normativos.

    Usa o Criterio II (variacao sobre a referencia) quando ha baseline, por ser
    mais sensivel; caso contrario recai no Criterio I (zona absoluta).
    """
    v_rms = float(indicators.get("iso_v_rms_mms", 0.0))
    zona = iso_zone(v_rms, machine_class)

    apoio: dict[str, float] = {}
    if fault_type in DOMINANT_INDICATOR:
        chave, _ = DOMINANT_INDICATOR[fault_type]
        if chave in indicators:
            apoio[chave] = float(indicators[chave])

    ref = (baseline or {}).get("iso_v_rms_mms")
    if ref:
        razao = v_rms / ref
        if razao >= RELATIVE_FAILURE:
            sev = FAILURE
        elif razao >= RELATIVE_WARNING:
            sev = WARNING
        else:
            sev = HEALTHY

        explicacao = (
            f"Velocidade de vibracao {razao:.1f}x a referencia registrada para "
            f"este motor ({v_rms:.3f} mm/s contra {ref:.3f} mm/s).")
        if fault_type in DOMINANT_INDICATOR and apoio:
            _, rotulo = DOMINANT_INDICATOR[fault_type]
            if baseline and DOMINANT_INDICATOR[fault_type][0] in baseline:
                r2 = (indicators[DOMINANT_INDICATOR[fault_type][0]]
                      / baseline[DOMINANT_INDICATOR[fault_type][0]])
                explicacao += f" A {rotulo} esta {r2:.1f}x a referencia."

        return PhysicalSeverity(
            severity=sev, criterion=SeverityCriterion.RELATIVE, iso_zone=zona,
            v_rms_mms=v_rms, machine_class=machine_class,
            ratio_to_baseline=razao, explanation=explicacao, supporting=apoio)

    # sem referencia: zona absoluta da norma
    sev = {"A": HEALTHY, "B": HEALTHY, "C": WARNING, "D": FAILURE}[zona]
    ab, bc, cd = ISO_ZONE_LIMITS[machine_class]
    explicacao = (
        f"Velocidade de {v_rms:.3f} mm/s: zona {zona} da ISO 10816-1 para "
        f"maquina classe {machine_class} (A/B={ab}, B/C={bc}, C/D={cd} mm/s). "
        f"Sem medicao de referencia deste motor, aplica-se o criterio de "
        f"magnitude absoluta, menos sensivel a degradacao incipiente.")

    return PhysicalSeverity(
        severity=sev, criterion=SeverityCriterion.ABSOLUTE, iso_zone=zona,
        v_rms_mms=v_rms, machine_class=machine_class,
        explanation=explicacao, supporting=apoio)
