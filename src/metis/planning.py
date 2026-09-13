from dataclasses import dataclass
from pathlib import Path
import re

from .models import Recipe
from .render import iter_template_files


class GenerationError(ValueError):
    """Raised when a project cannot be safely planned or generated."""


@dataclass(frozen=True)
class PlannedFile:
    action: str
    path: Path


@dataclass(frozen=True)
class GenerationPlan:
    recipe: str
    project_name: str
    destination: Path
    selections: dict[str, str]
    capabilities: tuple[str, ...]
    files: tuple[PlannedFile, ...]


def validate_project_name(project_name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", project_name):
        raise GenerationError(
            "project name must use letters, numbers, dots, underscores, or hyphens"
        )


def build_generation_plan(
    recipe: Recipe,
    project_name: str,
    destination_root: Path,
    answers: dict[str, str],
) -> GenerationPlan:
    validate_project_name(project_name)
    destination = destination_root / project_name
    if destination.exists() and any(destination.iterdir()):
        raise GenerationError(f"target directory already exists and is non-empty: {destination}")

    template_files = tuple(
        PlannedFile("CREATE", output_path)
        for _, output_path in iter_template_files(recipe.template_path)
    )
    files = (*template_files, PlannedFile("CREATE", Path(".metis/project.yaml")))
    return GenerationPlan(
        recipe=recipe.name,
        project_name=project_name,
        destination=destination,
        selections=dict(answers),
        capabilities=tuple(dict.fromkeys(recipe.capabilities)),
        files=files,
    )