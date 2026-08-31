"""Split treino/teste por especime — leave-one-specimen-out.

Decisao metodologica do projeto (documentar no TCC)
---------------------------------------------------
A unidade experimental independente do KAIST NAO e a janela, nem a sessao de
gravacao, nem a condicao de carga: e o **especime** — a montagem fisica da
bancada. O protocolo original montou cada defeito uma unica vez e o mediu sob
as tres cargas em sequencia (6 a 43 min de intervalo; ver Anexo A de
docs/01-inventario-dataset.md), portanto as tres sessoes de um mesmo defeito
compartilham rolamento, fixacao e alinhamento.

Isso descarta tres estrategias comuns:

  * split aleatorio 70/30 por janela -> janelas da mesma sessao nos dois lados;
  * split por sessao de gravacao      -> mesmo especime nos dois lados;
  * leave-one-load-out                -> mesmo especime nos dois lados.

Cada fold isola um dos 14 especimes de falha: as tres sessoes dele (0, 2 e 4 Nm)
vao inteiras para o teste, e nenhuma medicao daquela montagem aparece no treino.

Tratamento da classe HEALTHY
----------------------------
O dataset tem **um unico especime saudavel**, medido nas 3 cargas. Nao existe
particao capaz de avaliar generalizacao para uma maquina saudavel nunca vista —
limitacao do dataset, nao do metodo, e declarada como tal no TCC.

O melhor possivel e garantir que nenhuma JANELA saudavel seja compartilhada:
as 3 sessoes normais sao distribuidas entre 3 folds distintos. Assim cada sessao
do dataset aparece no conjunto de teste de exatamente um fold, e as predicoes
out-of-fold cobrem todas as janelas uma unica vez — base honesta para a matriz
de confusao agregada.
"""

from __future__ import annotations

from dataclasses import dataclass

from kaist.sessions import NORMAL


@dataclass(frozen=True)
class Fold:
    index: int
    held_out_specimen: str
    train_sessions: tuple[str, ...]
    test_sessions: tuple[str, ...]

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return (
            f"Fold({self.index}, held_out={self.held_out_specimen!r}, "
            f"train={len(self.train_sessions)}, test={len(self.test_sessions)})"
        )


def leave_one_specimen_out(sessions: dict) -> list[Fold]:
    """Gera um fold por especime de falha (14 folds).

    `sessions` e o dict retornado por `kaist.loaders.discover_sessions()`.
    """
    by_specimen: dict[str, list[str]] = {}
    normal_sessions: list[str] = []

    for sid, sf in sessions.items():
        spec = sf.meta.specimen_id
        if sf.meta.fault_family == NORMAL:
            normal_sessions.append(sid)
        else:
            by_specimen.setdefault(spec, []).append(sid)

    fault_specimens = sorted(by_specimen)
    normal_sessions.sort()
    n_folds = len(fault_specimens)

    if n_folds == 0:
        raise ValueError("nenhum especime de falha encontrado")

    # Distribui as sessoes normais uniformemente entre os folds, de forma
    # deterministica, para que cada janela saudavel seja testada uma unica vez.
    normal_for_fold: dict[int, list[str]] = {}
    if normal_sessions:
        step = n_folds / len(normal_sessions)
        for i, sid in enumerate(normal_sessions):
            normal_for_fold.setdefault(int(i * step), []).append(sid)

    all_sessions = set(sessions)
    folds: list[Fold] = []
    for i, spec in enumerate(fault_specimens):
        test = sorted(by_specimen[spec] + normal_for_fold.get(i, []))
        train = sorted(all_sessions - set(test))
        folds.append(Fold(i, spec, tuple(train), tuple(test)))

    _validate(folds, sessions)
    return folds


def _validate(folds: list[Fold], sessions: dict) -> None:
    """Falha alto e cedo se alguma invariante do split for violada."""
    seen_in_test: dict[str, int] = {}

    for f in folds:
        overlap = set(f.train_sessions) & set(f.test_sessions)
        if overlap:
            raise AssertionError(f"fold {f.index}: sessao em treino e teste: {overlap}")

        # nenhum especime de FALHA pode estar dos dois lados
        train_specs = {
            sessions[s].meta.specimen_id
            for s in f.train_sessions
            if sessions[s].meta.fault_family != NORMAL
        }
        test_specs = {
            sessions[s].meta.specimen_id
            for s in f.test_sessions
            if sessions[s].meta.fault_family != NORMAL
        }
        leaked = train_specs & test_specs
        if leaked:
            raise AssertionError(f"fold {f.index}: especime vazado: {leaked}")

        for s in f.test_sessions:
            seen_in_test[s] = seen_in_test.get(s, 0) + 1

    faltando = set(sessions) - set(seen_in_test)
    if faltando:
        raise AssertionError(f"sessoes nunca testadas: {sorted(faltando)}")
    repetidas = {s: n for s, n in seen_in_test.items() if n != 1}
    if repetidas:
        raise AssertionError(f"sessoes testadas mais de uma vez: {repetidas}")


# ---------------------------------------------------------------------------
# Hold-out de demonstracao
# ---------------------------------------------------------------------------
#: Especimes PERMANENTEMENTE excluidos do treino do modelo de producao.
#:
#: Motivacao: sem isso, qualquer demonstracao usaria dados que o modelo ja viu,
#: e a pergunta "ele ja conhecia este defeito?" teria como resposta honesta um
#: "sim" que invalida o que a demonstracao aparenta mostrar. Reservando
#: especimes inteiros, a demonstracao passa a exibir o comportamento real do
#: modelo diante de um defeito inedito.
#:
#: Escolheu-se um especime de cada familia de falha, de modo que os tres tipos
#: possam ser demonstrados com dado nunca visto. O custo e 9 das 45 sessoes
#: (20% do material de treino) — barato diante de poder afirmar, sem ressalva,
#: que o defeito apresentado e novo para o modelo.
HOLDOUT_SPECIMENS = (
    "bearing/outer_race/10",     # rolamento, pista externa 1,0 mm
    "misalignment/shaft/03",     # desalinhamento, nivel 2
    "unbalance/rotor/2239",      # desbalanceamento, 2.239 mg
)

#: Sessao normal reservada para demonstrar a condicao saudavel.
#:
#: LIMITACAO IMPORTANTE: existe um unico especime saudavel no dataset, entao
#: nao ha como reserva-lo por inteiro — sem ele, nao restaria HEALTHY no treino.
#: O que se reserva e uma SESSAO (uma condicao de carga) desse especime. E um
#: hold-out mais fraco que o dos especimes de falha: o modelo viu a mesma
#: montagem sob outras cargas. Deve ser apresentado com essa ressalva.
HOLDOUT_NORMAL_SESSION = "2Nm_Normal"


def is_holdout(meta) -> bool:
    """Indica se a sessao pertence ao hold-out de demonstracao."""
    return (meta.specimen_id in HOLDOUT_SPECIMENS
            or meta.session_id == HOLDOUT_NORMAL_SESSION)


def holdout_session_ids(sessions: dict) -> list[str]:
    """Sessoes reservadas, na ordem em que aparecem no dicionario."""
    return [sid for sid, sf in sessions.items() if is_holdout(sf.meta)]
