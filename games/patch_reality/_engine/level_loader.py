"""Load level definitions from JSON data files into Level objects."""

from __future__ import annotations

import json
from typing import Any

from .models import (
    Anchor,
    Level,
    LevelObjective,
    Resources,
    SceneObject,
)

_REQUIRED_FIELDS = ("id", "name", "phase", "premise", "objective", "turn_limit")


class LevelSchemaError(ValueError):
    """Raised when a level definition is missing required structure."""


class LevelLoader:
    """Loads level YAML into ``Level`` objects, resolving bilingual prose.

    Any prose value in the YAML may be either a plain string (used for every
    language) or a bilingual mapping ``{en: ..., zh: ...}``. The loader collapses
    every such mapping to the active-language string *before* building the
    ``Level``, so all downstream engine code keeps reading plain strings and is
    language-agnostic. Mechanical fields (costs, effects, diagnosis options,
    evidence tags, …) never use this shape, so they are left untouched.
    """

    def __init__(self, lang: str = "en") -> None:
        self.lang = lang if lang in ("zh", "en") else "en"

    @staticmethod
    def _is_bilingual(value: Any) -> bool:
        return (
            isinstance(value, dict)
            and bool(value)
            and set(value.keys()) <= {"en", "zh"}
        )

    def _pick(self, value: dict) -> Any:
        return value.get(self.lang) or value.get("en") or value.get("zh")

    def _localize(self, obj: Any) -> Any:
        """Recursively collapse bilingual ``{en, zh}`` maps to a single string."""
        if self._is_bilingual(obj):
            return self._pick(obj)
        if isinstance(obj, dict):
            return {key: self._localize(val) for key, val in obj.items()}
        if isinstance(obj, list):
            return [self._localize(item) for item in obj]
        return obj

    def load(self, path: str) -> Level:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise LevelSchemaError(f"Level file {path} did not parse to a mapping.")
        return self.load_dict(data)

    def load_dict(self, data: dict[str, Any]) -> Level:
        data = self._localize(data)
        for field_name in _REQUIRED_FIELDS:
            if field_name not in data:
                raise LevelSchemaError(f"Level is missing required field '{field_name}'.")

        objective = self._build_objective(data["objective"])
        resources = self._build_resources(data.get("initial_resources", {}))
        anchors = self._build_anchors(data.get("anchors", []))
        objects = self._build_objects(data.get("objects", {}))

        return Level(
            id=data["id"],
            name=data["name"],
            phase=int(data["phase"]),
            premise=data["premise"],
            objective=objective,
            turn_limit=int(data["turn_limit"]),
            initial_resources=resources,
            anchors=anchors,
            available_actions=list(data.get("available_actions", [])),
            objects=objects,
            valid_patches=dict(data.get("valid_patches", {})),
            predictions=dict(data.get("predictions", {})),
            scene_progression=list(data.get("scene_progression", [])),
            hidden_rules=list(data.get("hidden_rules", [])),
            triggers=list(data.get("triggers", [])),
            audit_entries=list(data.get("audit_entries", [])),
            diagnosis=dict(data.get("diagnosis", {})),
            patch_requirements=dict(data.get("patch_requirements", {})),
            focus_limit=(int(data["focus_limit"]) if data.get("focus_limit") is not None else None),
        )

    # -- builders --------------------------------------------------------

    def _build_objective(self, raw: Any) -> LevelObjective:
        if not isinstance(raw, dict) or "condition" not in raw:
            raise LevelSchemaError("objective must be a mapping with a 'condition'.")
        return LevelObjective(
            description=raw.get("description", ""),
            condition=raw["condition"],
        )

    def _build_resources(self, raw: dict[str, Any]) -> Resources:
        resources = Resources()
        for name, value in raw.items():
            if not hasattr(resources, name):
                raise LevelSchemaError(f"Unknown resource '{name}' in initial_resources.")
            setattr(resources, name, int(value))
        return resources

    def _build_anchors(self, raw: list) -> list[Anchor]:
        anchors = []
        for item in raw:
            anchors.append(
                Anchor(
                    name=item["name"],
                    integrity=int(item.get("integrity", 100)),
                    category=item.get("category", "memory"),
                    description=item.get("description", ""),
                )
            )
        return anchors

    def _build_objects(self, raw: dict[str, Any]) -> dict[str, SceneObject]:
        objects: dict[str, SceneObject] = {}
        for name, spec in raw.items():
            objects[name] = SceneObject(
                name=name,
                properties=dict(spec.get("properties", {})),
                observe_text=spec.get("observe_text", ""),
                patchable_properties=list(spec.get("patchable_properties", [])),
                evidence_tags=list(spec.get("evidence", [])),
            )
        return objects
