"""Severidade por criterio fisico, independente do aprendizado de maquina.

Decisao metodologica (documentar no TCC)
---------------------------------------
A severidade NAO e prevista pelo modelo. O rotulo de severidade disponivel no
dataset ("o menor nivel de cada familia e WARNING") e uma convencao
administrativa, sem correspondencia monotonica com o sinal: o defeito de
rolamento de 3,0 mm produz MENOS vibracao que o de 1,0 mm, e ha FAILURE com
amplitude menor que a do motor saudavel. Treinar um classificador sobre esse
rotulo produziu recall de 0,0 % para WARNING em especimes ineditos — o modelo
reconhecia qual montagem era, nao o quanto ela era grave.

Aqui a severidade e calculada, nao aprendida. O ML responde "que tipo de falha
e esta?"; esta camada responde "quao severa esta a condicao vibratoria?".
Os dois resultados sao apresentados juntos, e nenhum depende do outro.

Escolha da grandeza
-------------------
Velocidade RMS na banda 10-1000 Hz, que e a grandeza que a ISO 10816/20816
adota para avaliar severidade. A escolha tambem se sustenta empiricamente: e o
indicador que melhor ordena a severidade DENTRO de cada familia de falha
(Spearman +0,82 em rolamento, +0,92 em desalinhamento, +0,89 em
desbalanceamento), enquanto indicadores especificos falham nessa tarefa — a
aceleracao em alta frequencia detecta rolamento muito bem, mas gradua mal
(+0,13), porque nao cresce de forma monotonica com o tamanho do defeito.

Dois criterios, conforme a norma
--------------------------------
CRITERIO I  — magnitude absoluta, com as zonas A/B/C/D por classe de maquina.
              Aplicavel sempre, sem referencia previa.
CRITERIO II — variacao sobre uma referencia estabelecida para aquela maquina.
              Mais sensivel, exige uma medicao de referencia (opcional no
              sistema). E o criterio que discrimina na bancada do KAIST, onde
              os valores absolutos sao baixos demais para a zona sair de A.
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


#: Limiares do Criterio II, em multiplos da referencia saudavel.
#:
#: A ISO 10816-1 trata mudanca significativa em relacao a uma referencia, sem
#: fixar multiplicadores universais — eles dependem da maquina. Os valores
#: abaixo foram calibrados sobre a bancada do KAIST e devem ser reajustados
#: para outra instalacao; ficam explicitos aqui por isso.
#:
#: Como a distribuicao se comporta com estes cortes (razao mediana por especime):
#:      1,00x  normal                          -> HEALTHY
#:      1,05x  desbalanceamento 583 mg         -> HEALTHY
#:      1,39x  desbalanceamento 3.318 mg       -> HEALTHY
#:      2,00x  desalinhamento nivel 3          -> WARNING
#:      2,53x  rolamento externa 0,3 mm        -> WARNING
#:      3,09x  rolamento interna 1,0 mm        -> WARNING
#:      5,91x  rolamento interna 3,0 mm        -> FAILURE
#:     13,88x  rolamento externa 3,0 mm        -> FAILURE
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
