from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Question:
    id: str
    type: str
    message: str
    options: tuple[str, ...]
    default: str | None = None


@dataclass(frozen=True)
class Recipe:
    api_version: str
    kind: str
    name: str
    version: str
    description: str
    template_path: Path
    questions: tuple[Question, ...]
    capabilities: tuple[str, ...] = ()
    raw: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.raw is None:
            object.__setattr__(self, "raw", {})