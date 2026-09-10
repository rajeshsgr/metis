from pathlib import Path

import pytest

from metis.recipe import RecipeError, load_recipe


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schema/recipe.schema.json"
RECIPE = ROOT / "recipes/rag/recipe.yaml"


def test_loads_builtin_rag_recipe() -> None:
    recipe = load_recipe(RECIPE, SCHEMA)
    assert recipe.name == "rag"
    assert [question.id for question in recipe.questions] == [
        "vector_db",
        "llm",
        "embedding",
        "framework",
    ]


def test_rejects_malformed_yaml(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text("metadata: [", encoding="utf-8")

    with pytest.raises(RecipeError, match="invalid YAML"):
        load_recipe(recipe_path, SCHEMA)


def test_rejects_schema_failure(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text("kind: NotARecipe\n", encoding="utf-8")

    with pytest.raises(RecipeError, match="recipe validation failed"):
        load_recipe(recipe_path, SCHEMA)


def test_rejects_duplicate_question_ids(tmp_path: Path) -> None:
    content = RECIPE.read_text(encoding="utf-8").replace(
        "  - id: llm\n", "  - id: vector_db\n", 1
    )
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(content, encoding="utf-8")

    with pytest.raises(RecipeError, match="question IDs must be unique"):
        load_recipe(recipe_path, SCHEMA)