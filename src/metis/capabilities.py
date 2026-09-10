from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import yaml

COMPOSITE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "rag": ("python", "fastapi", "llm", "embeddings", "vector-db"),
    "agent": ("python", "fastapi", "llm", "agent-runtime", "state"),
}


class CapabilityError(ValueError):
    """Raised when capability definitions or resolution logic is invalid."""


def _normalize_name(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if not normalized:
        raise CapabilityError("capability names must not be empty")
    return normalized


@dataclass(frozen=True)
class Capability:
    name: str
    version: str
    description: str = ""
    provides: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityResolution:
    requested: tuple[str, ...]
    resolved: tuple[str, ...]
    keep: tuple[str, ...]
    add: tuple[str, ...]
    skip: tuple[str, ...]
    modify: tuple[str, ...] = ()


def _load_capability_definition(path: Path) -> Capability:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise CapabilityError(f"could not load capability definition {path}: {error}") from error

    if not isinstance(raw, dict):
        raise CapabilityError(f"capability definition {path} must contain a YAML object")

    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        raise CapabilityError(f"capability definition {path} has invalid metadata")

    name = metadata.get("name") or path.parent.name
    version = metadata.get("version", "0.1.0")
    provides = tuple(_normalize_name(item) for item in raw.get("provides", []))
    requires = tuple(_normalize_name(item) for item in raw.get("requires", []))

    return Capability(
        name=_normalize_name(str(name)),
        version=str(version),
        description=str(raw.get("metadata", {}).get("description", "")),
        provides=provides,
        requires=requires,
        raw=raw,
    )


def load_capabilities(root: Path) -> dict[str, Capability]:
    if not root.exists():
        return {}

    definitions: dict[str, Capability] = {}
    for capability_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        capability_file = capability_dir / "capability.yaml"
        if not capability_file.exists():
            continue

        capability = _load_capability_definition(capability_file)
        if capability.name in definitions:
            raise CapabilityError(f"duplicate capability definition: {capability.name}")
        definitions[capability.name] = capability

    return definitions


def _resolve_capability_names(names: Sequence[str], definitions: dict[str, Capability]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()

    def expand(name: str) -> tuple[str, ...]:
        normalized = _normalize_name(name)
        if normalized in COMPOSITE_CAPABILITIES:
            return COMPOSITE_CAPABILITIES[normalized]
        return (normalized,)

    def visit(name: str) -> None:
        for expanded_name in expand(name):
            normalized = _normalize_name(expanded_name)
            if normalized in seen:
                continue

            capability = definitions.get(normalized)
            if capability is None:
                raise CapabilityError(f"unknown capability: {normalized}")

            for dependency in capability.requires:
                visit(dependency)

            ordered.append(normalized)
            seen.add(normalized)

    for name in names:
        visit(name)

    return tuple(ordered)


def resolve_recipe_capabilities(recipe: Any, definitions: dict[str, Capability]) -> tuple[str, ...]:
    capabilities = recipe.raw.get("capabilities", []) if hasattr(recipe, "raw") else []
    if not capabilities:
        return ()

    return _resolve_capability_names(capabilities, definitions)


def reconcile_capabilities(
    requested: Sequence[str] | str,
    existing: Sequence[str],
    definitions: dict[str, Capability],
) -> CapabilityResolution:
    requested_names = [requested] if isinstance(requested, str) else list(requested)
    requested_normalized = tuple(_normalize_name(name) for name in requested_names)
    resolved = _resolve_capability_names(requested_normalized, definitions)
    existing_normalized = tuple(_normalize_name(name) for name in existing)
    existing_set = set(existing_normalized)

    keep = tuple(name for name in resolved if name in existing_set)
    add = tuple(name for name in resolved if name not in existing_set)
    skip = tuple(name for name in existing_normalized if name not in set(resolved))

    return CapabilityResolution(
        requested=requested_normalized,
        resolved=resolved,
        keep=keep,
        add=add,
        skip=skip,
    )
