from pathlib import Path

from .metadata import write_project_metadata
from .models import Recipe
from .planning import GenerationError, GenerationPlan, build_generation_plan
from .render import render_template_tree


def generate_project(
    recipe: Recipe,
    project_name: str,
    destination_root: Path,
    answers: dict[str, str],
    plan: GenerationPlan | None = None,
) -> Path:
    generation_plan = plan or build_generation_plan(
        recipe, project_name, destination_root, answers
    )
    destination = generation_plan.destination
    destination.mkdir(parents=True, exist_ok=True)
    context = {**generation_plan.selections, "project_name": generation_plan.project_name}
    render_template_tree(recipe.template_path, destination, context)
    write_project_metadata(
        destination,
        recipe,
        generation_plan.project_name,
        generation_plan.selections,
    )
    return destination