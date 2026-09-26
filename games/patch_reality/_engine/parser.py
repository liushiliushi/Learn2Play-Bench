"""Command parser: turns raw text into ParsedCommand intents.

This is the SYNTAX layer. It validates command grammar only — it does not know
about levels, scenes, or whether a target exists. Semantic validation happens in
the command handlers. The registry maps a ParsedCommand's verb to a handler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import PatchSpec


class ParseError(ValueError):
    """Raised when raw input cannot be parsed into a valid command."""


@dataclass
class ParsedCommand:
    verb: str
    args: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


# Verbs that take a single target argument: VERB <target>
_SINGLE_TARGET_VERBS = {
    "OBSERVE",
    "PREDICT",
    "INSPECT",
    "RECALL",
    "AUDIT",
    "ANCHOR",
    "CHECK_ANCHOR",
    "REINFORCE_ANCHOR",
}

# Verbs that take no arguments: VERB
_NO_ARG_VERBS = {"HELP"}

_KNOWN_VERBS = _SINGLE_TARGET_VERBS | _NO_ARG_VERBS | {"PATCH", "WAIT"}


class CommandParser:
    def parse(self, raw_input: str) -> ParsedCommand:
        text = raw_input.strip()
        if not text:
            raise ParseError("Empty command. Type an action such as 'OBSERVE coin'.")

        tokens = text.split()
        verb = tokens[0].upper()

        if verb not in _KNOWN_VERBS:
            raise ParseError(
                f"Unknown command '{tokens[0]}'. "
                f"Known commands: {', '.join(sorted(_KNOWN_VERBS))}."
            )

        if verb in _NO_ARG_VERBS:
            return ParsedCommand(verb, {}, text)
        if verb == "WAIT":
            return self._parse_wait(tokens, text)
        if verb == "PATCH":
            return ParsedCommand("PATCH", {"spec": self._parse_patch(tokens)}, text)
        return self._parse_single_target(verb, tokens, text)

    # -- per-verb parsers ------------------------------------------------

    def _parse_wait(self, tokens: list[str], raw: str) -> ParsedCommand:
        turns = 1
        if len(tokens) > 1:
            try:
                turns = int(tokens[1])
            except ValueError:
                raise ParseError(f"WAIT expects a number of turns, got '{tokens[1]}'.")
            if turns < 1:
                raise ParseError("WAIT count must be at least 1.")
        return ParsedCommand("WAIT", {"turns": turns}, raw)

    def _parse_single_target(self, verb: str, tokens: list[str], raw: str) -> ParsedCommand:
        if len(tokens) < 2:
            if verb == "AUDIT":
                return ParsedCommand(verb, {"target": "last_patch"}, raw)
            raise ParseError(f"{verb} requires a target, e.g. '{verb} <name>'.")
        return ParsedCommand(verb, {"target": tokens[1]}, raw)

    def _parse_patch(self, tokens: list[str]) -> PatchSpec:
        # Grammar:
        #   PATCH <target>.<property> <change...> FOR <duration...> SCOPE <scope...> PAY <resource...>
        upper = [t.upper() for t in tokens]

        for_idx = self._find_keyword(upper, "FOR")
        scope_idx = self._find_keyword(upper, "SCOPE")
        pay_idx = self._find_keyword(upper, "PAY")

        if not (1 < for_idx < scope_idx < pay_idx < len(tokens)):
            raise ParseError(
                "PATCH syntax: PATCH <target>.<property> <change> "
                "FOR <duration> SCOPE <scope> PAY <resource>"
            )

        target_property = tokens[1]
        if "." not in target_property:
            raise ParseError(
                f"PATCH target must be '<target>.<property>', got '{target_property}'."
            )
        target, prop = target_property.split(".", 1)
        if not target or not prop:
            raise ParseError(
                f"PATCH target must be '<target>.<property>', got '{target_property}'."
            )

        change = " ".join(tokens[2:for_idx])
        duration = " ".join(tokens[for_idx + 1 : scope_idx])
        scope = " ".join(tokens[scope_idx + 1 : pay_idx])
        pay = " ".join(tokens[pay_idx + 1 :])

        if not change:
            raise ParseError("PATCH requires a change value before FOR.")
        if not duration:
            raise ParseError("PATCH requires a duration after FOR.")
        if not scope:
            raise ParseError("PATCH requires a scope after SCOPE.")
        if not pay:
            raise ParseError("PATCH requires a resource after PAY.")

        return PatchSpec(
            target=target,
            property=prop,
            change=change,
            duration=duration,
            scope=scope,
            pay_resource=pay,
        )

    @staticmethod
    def _find_keyword(upper_tokens: list[str], keyword: str) -> int:
        try:
            return upper_tokens.index(keyword)
        except ValueError:
            return -1
