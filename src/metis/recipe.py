from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .models import Question, Recipe


class RecipeError(ValueError):
    """Raised when a recipe cannot be loaded or validated."""


def load_recipe(recipe_path: Path, schema_path: Path) -> Recipe:
    try:
        raw = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RecipeError(f"invalid YAML in {recipe_path}: {error}") from error
    except OSError as error:
        raise RecipeError(f"could not read recipe {recipe_path}: {error}") from error

    if not isinstance(raw, dict):
        raise RecipeError("recipe must contain a YAML object")

    try:
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RecipeError(f"could not read recipe schema {schema_path}: {error}") from error

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(raw), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "recipe"
        raise RecipeError(f"recipe validation failed at {location}: {error.message}")

    questions_data = raw["questions"]
    question_ids = [question["id"] for question in questions_data]
    if len(question_ids) != len(set(question_ids)):
        raise RecipeError("recipe validation failed: question IDs must be unique")

    template_path = recipe_path.parent / raw["template"]["path"]
    questions = tuple(
        Question(
            id=question["id"],
            type=question["type"],
            message=question["message"],
            options=tuple(question["options"]),
            default=question.get("default"),
        )
        for question in questions_data
    )
    capabilities = tuple(raw.get("capabilities", ()))
    metadata = raw["metadata"]
    return Recipe(
        api_version=raw["apiVersion"],
        kind=raw["kind"],
        name=metadata["name"],
        version=metadata["version"],
        description=metadata.get("description", ""),
        template_path=template_path,
        questions=questions,
        capabilities=capabilities,
        raw=raw,
    )