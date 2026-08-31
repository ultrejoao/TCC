"""Gera arquivos de sinal prontos para testar o sistema pela interface.

As amostras saem dos ESPECIMES RESERVADOS — montagens que o modelo nunca viu no
treino (ver ml/kaist/splits.py). Diagnosticar um desses arquivos mostra o
comportamento real diante de um defeito inedito, e nao a memoria do treino.

Por que recortar em vez de usar o .mat original: os arquivos do dataset tem 49 a
98 MB, acima do limite de upload da API (50 MB). Alem disso, o .mat traz quatro
acelerometros, enquanto um instrumento de campo fornece um canal — recortar um
canal aproxima a demonstracao do uso real.

Saida: ml/data/demo_samples/, com um CSV por condicao e um README explicando o
que cada arquivo contem.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, ML_ROOT  # noqa: E402
from kaist.loaders import discover_sessions, load_vibration  # noqa: E402
from kaist.splits import HOLDOUT_NORMAL_SESSION, HOLDOUT_SPECIMENS  # noqa: E402

SEGUNDOS = 5.0
CANAL = 0                       # acc1: radial no mancal proximo ao rotor
DESTINO = ML_ROOT / "data" / "demo_samples"

DESCRICAO = {
    "bearing/outer_race/10": "rolamento com defeito de 1,0 mm na pista externa",
    "misalignment/shaft/03": "desalinhamento de eixo, nivel 2 de 3",
    "unbalance/rotor/2239": "desbalanceamento de rotor, 2.239 mg",
}


def main() -> None:
    sessions = discover_sessions()
    DESTINO.mkdir(parents=True, exist_ok=True)

    linhas_readme = [
        "# Amostras para demonstracao",
        "",
        "Sinais recortados do dataset KAIST para testar o sistema pela interface.",
        "",
        "**Todos vem de especimes RESERVADOS**: montagens excluidas do treino do",
        "modelo de producao. O diagnostico sobre estes arquivos mostra o",
        "comportamento diante de um defeito inedito.",
        "",
        f"Cada arquivo tem {SEGUNDOS:.0f} s de um canal de vibracao, amostrado a",
        "25.600 Hz, em m/s^2.",
        "",
        "## Como usar",
        "",
        "Na tela **Coletar**, escolha o motor, envie o arquivo e informe:",
        "",
        "- taxa de amostragem: **25600**",
        "- unidade: **m/s^2**",
        "- carga: conforme o nome do arquivo (0, 2 ou 4 Nm)",
        "",
        "Para ver a severidade pelo criterio de variacao (mais sensivel), envie",
        f"antes o arquivo `{HOLDOUT_NORMAL_SESSION}.csv` marcado como **medicao de",
        "referencia** — ele e a condicao saudavel do mesmo motor.",
        "",
        "## Arquivos",
        "",
        "| arquivo | condicao real | carga |",
        "| :--- | :--- | ---: |",
    ]

    gerados = 0
    for sid, sf in sessions.items():
        meta = sf.meta
        reservado = (meta.specimen_id in HOLDOUT_SPECIMENS
                     or sid == HOLDOUT_NORMAL_SESSION)
        if not reservado:
            continue

        vib, fs = load_vibration(sf.vibration_path)
        trecho = vib[: int(fs * SEGUNDOS), CANAL]

        destino = DESTINO / f"{sid}.csv"
        np.savetxt(destino, trecho, delimiter=",", fmt="%.6f")

        cond = ("condicao normal (saudavel)" if meta.fault_family == "normal"
                else DESCRICAO.get(meta.specimen_id, meta.specimen_id))
        linhas_readme.append(f"| `{sid}.csv` | {cond} | {meta.load_nm} Nm |")
        print(f"  {destino.name:26s} {destino.stat().st_size/1e6:5.1f} MB  {cond}")
        gerados += 1

    linhas_readme += [
        "",
        "## O que esperar",
        "",
        "O modelo identifica o TIPO de falha; a severidade vem de criterio fisico",
        "(ISO 10816). Sem medicao de referencia, a severidade usa a magnitude",
        "absoluta e tende a subestimar — nesta bancada os valores sao baixos, e",
        "mesmo um defeito severo permanece na zona B.",
        "",
        "A condicao normal e o caso mais dificil: o modelo acerta o tipo em 77%",
        "dos casos, e pode confundi-la com desalinhamento. Isso esta documentado",
        "em docs/02-resultados-baseline.md.",
    ]

    (DESTINO / "README.md").write_text("\n".join(linhas_readme), encoding="utf-8")
    print(f"\n{gerados} amostras em {DESTINO}")
    print(f"instrucoes em {DESTINO / 'README.md'}")


if __name__ == "__main__":
    main()
