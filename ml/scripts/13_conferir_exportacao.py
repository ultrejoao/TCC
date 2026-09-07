"""Confere um arquivo exportado do coletor contra o que o equipamento mostrou.

Por que isto existe
-------------------
A tela do CSI 2140 mostra um escalar ("Global 1,3541 g Pico"); a exportacao
traz a forma de onda. Os dois deveriam fechar, mas a exportacao pode trocar a
unidade (m/s^2 em vez de g), a deteccao (RMS em vez de pico) ou entregar o
sinal ainda em volts do sensor, esperando que a sensibilidade em mV/g seja
aplicada depois.

Nenhuma dessas divergencias gera erro. O sinal entra no modelo com a amplitude
errada por um fator constante e sai um diagnostico plausivel — o pior tipo de
falha, porque nao se anuncia.

Como o script resolve
---------------------
O valor da tela e a referencia. O script calcula do arquivo todas as
combinacoes plausiveis de unidade x deteccao e mostra qual delas reproduz o
numero do coletor. A combinacao que fecha e a interpretacao correta do arquivo.

Uso
---
    python scripts/13_conferir_exportacao.py ARQUIVO --global 1.3541 \\
        --deteccao pico --unidade g [--fs 25600] [--coluna 1]

Se o `--global` for omitido, o script apenas descreve o arquivo, o que ja serve
para verificar taxa de amostragem, duracao e presenca de offset DC.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MS2_TO_G  # noqa: E402

G = 1.0 / MS2_TO_G  # 9,80665 m/s^2 por g

#: Erro relativo abaixo do qual duas grandezas sao consideradas a mesma.
TOLERANCIA = 0.05


def br(valor: float, casas: int = 2) -> str:
    """Formata no padrao brasileiro: ponto de milhar, virgula decimal."""
    return f"{valor:,.{casas}f}".translate(str.maketrans(",.", ".,"))


#: Como o arquivo pode estar escalado, e o fator que converte para g.
UNIDADES = {
    "g": ("ja em g", 1.0),
    "m/s^2": ("aceleracao em m/s^2", MS2_TO_G),
    "mm/s^2": ("aceleracao em mm/s^2", MS2_TO_G / 1000.0),
    "V (100 mV/g)": ("volts, sensor de 100 mV/g", 10.0),
    "V (500 mV/g)": ("volts, sensor de 500 mV/g", 2.0),
}


def deteccoes(x: np.ndarray) -> dict[str, float]:
    """Os quatro valores que um coletor pode chamar de 'global'."""
    ac = x - x.mean()  # o global e sempre AC; o offset DC nao conta
    rms = float(np.sqrt(np.mean(ac**2)))
    return {
        "pico verdadeiro": float(np.abs(ac).max()),
        "RMS": rms,
        "pico derivado (RMS x 1,414)": rms * np.sqrt(2.0),
        "pico a pico / 2": float(ac.max() - ac.min()) / 2.0,
    }


def ler(caminho: Path, coluna: int | None) -> tuple[np.ndarray, float | None]:
    """Le um arquivo texto de uma ou duas colunas. Devolve (sinal, fs inferida)."""
    dados = np.loadtxt(caminho, delimiter=None if caminho.suffix != ".csv" else ",",
                       comments=("#", "%"), ndmin=2)

    if dados.shape[1] == 1:
        return dados[:, 0], None

    if coluna is not None:
        return dados[:, coluna], None

    # duas colunas costumam ser (tempo, amplitude): a taxa sai do proprio tempo
    t = dados[:, 0]
    passos = np.diff(t)
    if passos.size and np.all(passos > 0) and passos.std() < passos.mean() * 0.01:
        return dados[:, 1], float(1.0 / passos.mean())

    return dados[:, 1], None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arquivo", type=Path)
    ap.add_argument("--global", dest="valor_tela", type=float,
                    help="valor global mostrado na tela do coletor")
    ap.add_argument("--deteccao", default="pico", choices=["pico", "rms", "p2p"],
                    help="deteccao indicada na tela (padrao: pico)")
    ap.add_argument("--unidade", default="g", help="unidade indicada na tela")
    ap.add_argument("--fs", type=float, help="taxa de amostragem, se conhecida")
    ap.add_argument("--coluna", type=int, help="indice da coluna de amplitude")
    args = ap.parse_args()

    sinal, fs_inferida = ler(args.arquivo, args.coluna)
    fs = args.fs or fs_inferida

    print(f"\narquivo   {args.arquivo.name}")
    print(f"amostras  {br(len(sinal), 0)}")
    if fs:
        print(f"taxa      {br(fs)} Hz  ->  {br(len(sinal)/fs, 3)} s")
        print(f"          fmax implicito {br(fs/2.56, 0)} Hz")
    else:
        print("taxa      NAO consta no arquivo — precisa vir do cabecalho ou da tela")

    offset = float(sinal.mean())
    print(f"offset DC {offset:+.5f}   (removido antes de qualquer calculo)")

    d = deteccoes(sinal)
    print("\nvalores calculados do arquivo, como ele esta:")
    for nome, v in d.items():
        print(f"  {nome:30s} {v:12.5f}")

    if args.valor_tela is None:
        print("\nsem --global: nenhuma conferencia de escala foi feita.")
        return

    alvo = {"pico": "pico verdadeiro", "rms": "RMS",
            "p2p": "pico a pico / 2"}[args.deteccao]

    print(f"\ntela: {args.valor_tela} {args.unidade} ({args.deteccao})")
    print("=" * 62)
    print("QUAL INTERPRETACAO DO ARQUIVO REPRODUZ A TELA")
    print("=" * 62)
    print(f"{'se o arquivo estiver em':32s} {'valor em g':>12s} {'erro':>10s}")

    candidatos = []
    for rotulo, (_, para_g) in UNIDADES.items():
        for nome_det, bruto in d.items():
            valor_g = bruto * para_g
            erro = abs(valor_g - args.valor_tela) / max(args.valor_tela, 1e-12)
            candidatos.append((erro, nome_det != alvo, rotulo, nome_det, valor_g))

    # ordena por erro e, em empate, favorece a deteccao declarada na tela
    candidatos.sort(key=lambda c: (round(c[0], 3), c[1]))
    vistos: set[str] = set()
    for erro, _, rotulo, nome_det, valor_g in candidatos:
        if rotulo in vistos:
            continue
        vistos.add(rotulo)
        marca = " <-- fecha" if erro < TOLERANCIA and nome_det == alvo else ""
        print(f"{rotulo:32s} {valor_g:12.5f} {erro:9.1%}{marca}")
        if nome_det != alvo and erro < TOLERANCIA:
            print(f"{'':32s}   (fecha como {nome_det}, nao como {alvo})")

    erro, _, rotulo, nome_det, _ = candidatos[0]
    print()
    if erro < TOLERANCIA and nome_det == alvo:
        print(f"CONSISTENTE: o arquivo esta em {rotulo} e a deteccao confere.")
        if rotulo != args.unidade:
            print(f"ATENCAO: a tela diz {args.unidade}, o arquivo esta em "
                  f"{rotulo} — converter antes de enviar ao sistema.")
    elif erro < TOLERANCIA:
        print(f"ESCALA OK, DETECCAO DIVERGE: o arquivo em {rotulo} reproduz a")
        print(f"tela, mas como '{nome_det}' e nao como '{alvo}'. Conferir o")
        print("campo 'Modo Global' no coletor (Digital calcula sobre a onda;")
        print("Derivado estima o pico a partir do RMS e nao fecha com o sinal).")
    else:
        print(f"NAO FECHA: a melhor hipotese ({rotulo}, {nome_det}) ainda erra")
        print(f"{erro:.1%}. Causas possiveis, em ordem de probabilidade:")
        print("  1. a forma de onda exportada nao e do mesmo ponto/data da tela;")
        print("  2. o ponto e PeakVue — o global vem do envelope, nao da onda;")
        print("  3. filtro ou integracao aplicados so em um dos dois caminhos;")
        print("  4. sensibilidade do sensor diferente da assumida.")


if __name__ == "__main__":
    main()
