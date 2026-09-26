"""Objective / scene condition evaluator.

Conditions are referenced by name from level data. Two generic forms are built
in so most levels need no Python at all:

    flag:<name>              True when scene_flags[<name>] is truthy
    not_flag:<name>          True when scene_flags[<name>] is falsy/absent
    evidence:<tag>           True when <tag> is in state.evidence_tags (hard mode)
    all:<a>|<b>|...          True when every nested condition is true
    any:<a>|<b>|...          True when at least one nested condition is true
    anchor:<name>>=<value>   True when an anchor has at least that integrity

Named conditions for special logic can be added to _REGISTRY.
"""

from __future__ import annotations

from typing import Callable

from .state import GameState

# Named conditions with bespoke logic.
_REGISTRY: dict[str, Callable[[GameState], bool]] = {
    "always_true": lambda state: True,
}


def register_condition(name: str, fn: Callable[[GameState], bool]) -> None:
    _REGISTRY[name] = fn


def evaluate_condition(name: str, state: GameState) -> bool:
    if name.startswith("all:"):
        return all(evaluate_condition(part, state) for part in _split_parts(name[4:]))
    if name.startswith("any:"):
        return any(evaluate_condition(part, state) for part in _split_parts(name[4:]))
    if name.startswith("anchor:"):
        return _evaluate_anchor_condition(name[len("anchor:"):], state)
    if name.startswith("flag:"):
        return bool(state.scene_flags.get(name[len("flag:"):], False))
    if name.startswith("evidence:"):
        return name[len("evidence:"):] in state.evidence_tags
    if name.startswith("not_flag:"):
        return not bool(state.scene_flags.get(name[len("not_flag:"):], False))
    fn = _REGISTRY.get(name)
    if fn is None:
        raise KeyError(f"Unknown condition '{name}'.")
    return fn(state)


def _split_parts(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]


def _evaluate_anchor_condition(raw: str, state: GameState) -> bool:
    for operator in (">=", "<=", "==", ">", "<"):
        if operator not in raw:
            continue
        anchor_name, threshold_text = raw.split(operator, 1)
        anchor = state.get_anchor(anchor_name.strip())
        if anchor is None:
            return False
        threshold = int(threshold_text.strip())
        if operator == ">=":
            return anchor.integrity >= threshold
        if operator == "<=":
            return anchor.integrity <= threshold
        if operator == "==":
            return anchor.integrity == threshold
        if operator == ">":
            return anchor.integrity > threshold
        if operator == "<":
            return anchor.integrity < threshold
    raise KeyError(f"Unknown anchor condition 'anchor:{raw}'.")
