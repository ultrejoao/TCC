"""Split treino/teste por especime: 14 folds, um por montagem fisica.

    protocolo                 tipo    severidade
    aleatorio por janela     100,0%      100,0%
    leave-one-load-out        80,6%       95,3%
    leave-one-specimen-out    88,7%       63,0%
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

    # Distribui as sessoes normais uniforme entre os folds, de forma
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

HOLDOUT_SPECIMENS = (
    "bearing/outer_race/10",     # rolamento, pista externa 1,0 mm
    "misalignment/shaft/03",     # desalinhamento, nivel 2
    "unbalance/rotor/2239",      # desbalanceamento, 2.239 mg
)

HOLDOUT_NORMAL_SESSION = "2Nm_Normal"


def is_holdout(meta) -> bool:
    """Indica se a sessao pertence ao hold-out de demonstracao."""
    return (meta.specimen_id in HOLDOUT_SPECIMENS
            or meta.session_id == HOLDOUT_NORMAL_SESSION)


def holdout_session_ids(sessions: dict) -> list[str]:
    """Sessoes reservadas, na ordem em que aparecem no dicionario."""
    return [sid for sid, sf in sessions.items() if is_holdout(sf.meta)]
