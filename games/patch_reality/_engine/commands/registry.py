"""Command registry: maps verbs to handler classes and instantiates them."""

from __future__ import annotations

from ..parser import ParsedCommand
from .anchor import AnchorCommand, CheckAnchorCommand, ReinforceAnchorCommand
from .audit import AuditCommand
from .base import Command
from .help_cmd import HelpCommand
from .observe import ObserveCommand
from .patch_cmd import PatchCommand
from .predict import PredictCommand
from .wait import WaitCommand


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, type[Command]] = {}

    def register(self, verb: str, handler_cls: type[Command]) -> None:
        self._handlers[verb.upper()] = handler_cls

    def is_registered(self, verb: str) -> bool:
        return verb.upper() in self._handlers

    def verbs(self) -> list[str]:
        return sorted(self._handlers)

    def create(self, parsed: ParsedCommand) -> Command:
        handler_cls = self._handlers.get(parsed.verb.upper())
        if handler_cls is None:
            raise KeyError(f"No handler registered for verb '{parsed.verb}'.")
        return handler_cls(parsed)


def default_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register("OBSERVE", ObserveCommand)
    reg.register("PREDICT", PredictCommand)
    reg.register("PATCH", PatchCommand)
    reg.register("AUDIT", AuditCommand)
    reg.register("WAIT", WaitCommand)
    reg.register("ANCHOR", AnchorCommand)
    reg.register("CHECK_ANCHOR", CheckAnchorCommand)
    reg.register("REINFORCE_ANCHOR", ReinforceAnchorCommand)
    reg.register("HELP", HelpCommand)
    return reg
