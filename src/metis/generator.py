import re
from pathlib import Path

from .metadata import write_project_metadata
from .models import Recipe
from .render import render_template_tree


class GenerationError(ValueError):
    """Raised when a project cannot be safely generated."""


def validate_project_name(project_name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", project_name):
        raise GenerationError(
            "project name must use letters, numbers, dots, underscores, or hyphens"
        )


def generate_project(recipe: Recipe, project_name: str, destination_root: Path, answers: dict[str, str]) -> Path:
    validate_project_name(project_name)
    destination = destination_root / project_name
    if destination.exists() and any(destination.iterdir()):
        raise GenerationError(f"target directory already exists and is non-empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    context = {**answers, "project_name": project_name}
    render_template_tree(recipe.template_path, destination, context)
    write_project_metadata(destination, recipe, project_name, answers)
    return destination