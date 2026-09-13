from pathlib import Path

import pytest

from metis.planning import GenerationError, build_generation_plan
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
RECIPE = load_recipe(ROOT / "recipes/rag/recipe.yaml", ROOT / "schema/recipe.schema.json")


def test_build_generation_plan_uses_rendered_template_paths_and_metadata(tmp_path: Path) -> None:
    selections = {
        "vector_db": "chroma",
        "llm": "anthropic",
        "embedding": "huggingface",
        "framework": "fastapi",
    }

    plan = build_generation_plan(RECIPE, "demo", tmp_path, selections)

    assert plan.destination == tmp_path / "demo"
    assert plan.selections == selections
    assert plan.capabilities == ("python", "fastapi", "llm", "embeddings", "vector-db")
    planned_paths = {planned_file.path.as_posix() for planned_file in plan.files}
    assert ".metis/project.yaml" in planned_paths
    assert "app/main.py" in planned_paths
    assert "app/main.py.j2" not in planned_paths
    assert all(planned_file.action == "CREATE" for planned_file in plan.files)
    assert not plan.destination.exists()


def test_build_generation_plan_rejects_non_empty_destination_without_mutation(tmp_path: Path) -> None:
    destination = tmp_path / "demo"
    destination.mkdir()
    existing = destination / "keep.txt"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(GenerationError, match="non-empty"):
        build_generation_plan(RECIPE, "demo", tmp_path, {})

    assert existing.read_text(encoding="utf-8") == "keep"