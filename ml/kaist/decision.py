"""Matriz de decisao: cruza a predicao do modelo com a evidencia fisica.

Motivacao
---------
O modelo tem um ponto cego conhecido e documentado: sob leave-one-specimen-out
o recall de WARNING e 0,0%. Um sistema que sempre crava uma classe esconde essa
limitacao; um que sinaliza "as evidencias nao batem" e honesto sobre ela e
direciona a inspecao humana para onde ela rende mais.

Como a independencia e preservada
---------------------------------
Os indicadores normativos tambem sao features do modelo, entao perguntar apenas
"o indicador esta alto?" seria circular — o modelo ja viu aquele numero. A
segunda opiniao aqui e construida sobre as PROPORCOES ADIMENSIONAIS entre
indicadores, que codificam a *assinatura* da falha e nao sua magnitude:

    p_1x = v_1x / v_rms      fracao da energia na rotacao   -> desbalanceamento
    p_2x = v_2x / v_rms      fracao em 2x a rotacao
    p_hf = a_hf / v_rms      peso da alta frequencia        -> rolamento

A classificacao fisica e um vizinho-mais-proximo sobre protótipos por familia,
ajustados APENAS no conjunto de treino de cada fold.

Assinaturas medidas neste dataset (mediana por familia):

    familia          p_1x    p_2x    p_hf
    desbalanceamento 0,608   0,187   2,76     <- 1x dominante
    normal           0,328   0,213   2,07
    desalinhamento   0,299   0,178   4,16     <- alta frequencia
    rolamento        0,085   0,087   4,79     <- alta frequencia dominante

Nota para o TCC: a assinatura classica de literatura "desalinhamento -> 2x" NAO
se confirmou aqui — o p_2x do desalinhamento (0,178) e menor que o da condicao
normal (0,213). Os protótipos sao portanto empiricos, ajustados aos dados, e nao
transcritos da teoria.

Validacao empirica (leave-one-specimen-out, alvo fault_type):

    concordancia em 65,4% das janelas
    acuracia do modelo quando concordam: 91,5%
    acuracia do modelo quando discordam: 83,3%
    -> discordar dobra a taxa de erro (8,5% -> 16,7%)
    -> 35% das janelas concentram 51% dos erros

E um priorizador de confianca, NAO um detector de erro: mesmo discordando o
modelo acerta 83% das vezes, e metade dos erros ocorre com evidencias
concordantes. Comunicar como nivel de confianca, nunca como veredito.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_EPS = 1e-9

PROPORTION_NAMES = ["p_1x", "p_2x", "p_hf"]


def physical_proportions(indicators: dict[str, float]) -> dict[str, float]:
    """Converte os indicadores normativos nas proporcoes adimensionais."""
    v_rms = indicators["iso_v_rms_mms"] + _EPS
    return {
        "p_1x": indicators["iso_v_1x_mms"] / v_rms,
        "p_2x": indicators["iso_v_2x_mms"] / v_rms,
        "p_hf": indicators["iso_a_hf_g"] / v_rms,
    }


@dataclass
class PhysicalSignature:
    """Segunda opiniao baseada na assinatura fisica, independente do modelo."""

    classes: list[str]
    prototypes: np.ndarray   # (n_classes, 3) medianas em log-espaco
    scale: np.ndarray        # (3,) desvio-padrao para normalizar as distancias

    @classmethod
    def fit(cls, proportions: np.ndarray, labels: np.ndarray,
            classes: list[str]) -> "PhysicalSignature":
        """Ajusta os protótipos. Deve receber APENAS dados de treino."""
        log_p = np.log(proportions + _EPS)
        protos = np.array([np.median(log_p[labels == i], axis=0)
                           for i in range(len(classes))])
        return cls(classes=classes, prototypes=protos,
                   scale=log_p.std(axis=0) + _EPS)

    def distances(self, proportions: np.ndarray) -> np.ndarray:
        """Distancia normalizada de cada amostra a cada protótipo."""
        log_p = np.log(np.atleast_2d(proportions) + _EPS)
        return np.linalg.norm(
            (log_p[:, None, :] - self.prototypes[None, :, :]) / self.scale, axis=2)

    def predict(self, proportions: np.ndarray) -> np.ndarray:
        return self.distances(proportions).argmin(axis=1)


@dataclass
class Decision:
    """Resultado da matriz de decisao para uma medicao."""

    fault_type: str
    fault_type_proba: float
    severity: str
    severity_proba: float
    physical_type: str          # o que a assinatura fisica indica
    agreement: bool
    confidence: float           # 0..1, continuo
    recommendation: str
    indicators: dict[str, float]
    proportions: dict[str, float]
    baseline_change: dict[str, float] | None = None


def _confidence(model_proba: float, agree: bool,
                d_predicted: float, d_best: float) -> float:
    """Confianca continua combinando certeza do modelo e apoio da fisica.

    A penalidade e proporcional a quanto a assinatura fisica se afasta da classe
    predita — nao um degrau binario, para permitir calibrar quanto se sinaliza e
    evitar fadiga de alarme.
    """
    gap = max(d_predicted - d_best, 0.0)
    physical_support = float(np.exp(-gap))    # 1.0 quando a fisica concorda
    return float(np.clip(model_proba * (0.5 + 0.5 * physical_support), 0.0, 1.0))


#: Tolerancia de concordancia, em unidades de distancia normalizada.
#: PADRAO 0.0 = concordancia estrita: a fisica apoia a classe predita apenas se
#: ela for o protótipo mais proximo.
#:
#: Calibracao empirica (ml/scripts/05_calibrate_decision.py):
#:
#:   margem  sinalizado  erro sinaliz.  erro nao sin.  ganho  erros capturados
#:     0,00      34,6%         16,7%           8,5%    2,0x        51%   <- adotado
#:     0,50      22,2%         21,5%           8,4%    2,6x        42%
#:     0,75      11,5%         25,4%           9,5%    2,7x        26%
#:     1,00       6,5%          1,0%          12,0%    0,1x         1%
#:
#: Por que 0,0 e nao um valor maior: margens maiores elevam o "ganho" (a taxa de
#: erro concentrada no que se sinaliza) mas CAPTURAM MENOS ERROS. Trocar
#: sensibilidade por precisao contraria a premissa do projeto, em que um falso
#: negativo de FAILURE custa mais que uma inspecao desnecessaria.
#:
#: ACHADO CONTRAINTUITIVO, importante para o TCC: a partir de ~1,0 o sinal se
#: INVERTE — as janelas sinalizadas passam a errar MENOS que as nao sinalizadas.
#: Um afastamento fisico extremo indica que a assinatura de referencia e que
#: esta inadequada (tipicamente em rolamento, onde o modelo acerta 100%), e nao
#: que o modelo errou. O parametro portanto NAO e monotonico: aumenta-lo "para
#: sinalizar menos" quebra a camada silenciosamente. Alterar apenas com nova
#: calibracao.
AGREEMENT_MARGIN = 0.0


def decide(fault_type: str, fault_type_proba: float,
           severity: str, severity_proba: float,
           indicators: dict[str, float],
           signature: PhysicalSignature,
           baseline_change: dict[str, float] | None = None,
           confidence_threshold: float = 0.60,
           agreement_margin: float = AGREEMENT_MARGIN) -> Decision:
    """Cruza predicao do modelo e evidencia fisica numa decisao unica."""
    props = physical_proportions(indicators)
    vec = np.array([[props[n] for n in PROPORTION_NAMES]])

    dists = signature.distances(vec)[0]
    best = int(dists.argmin())
    physical_type = signature.classes[best]

    idx = signature.classes.index(fault_type) if fault_type in signature.classes else best
    # concordancia com tolerancia: a fisica APOIA a classe predita se ela estiver
    # dentro da margem, ainda que nao seja o protótipo mais proximo
    agree = bool(dists[idx] - dists[best] <= agreement_margin)
    conf = _confidence(fault_type_proba, agree, float(dists[idx]), float(dists[best]))

    if agree and conf >= confidence_threshold:
        rec = "Evidencias concordantes: diagnostico consistente."
    elif agree:
        rec = "Evidencias concordantes, porem o modelo tem baixa certeza."
    else:
        rec = (f"Evidencias discordantes: o modelo indica '{fault_type}', "
               f"mas a assinatura de vibracao e compativel com '{physical_type}'. "
               f"Inspecao recomendada.")

    if agree and physical_type != fault_type:
        rec += (f" (assinatura mais proxima seria '{physical_type}', "
                f"dentro da margem de tolerancia)")

    if severity == "FAILURE":
        rec += " Severidade prevista FAILURE: priorizar intervencao."

    return Decision(
        fault_type=fault_type, fault_type_proba=fault_type_proba,
        severity=severity, severity_proba=severity_proba,
        physical_type=physical_type, agreement=agree, confidence=conf,
        recommendation=rec, indicators=indicators, proportions=props,
        baseline_change=baseline_change)
