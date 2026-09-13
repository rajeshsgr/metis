from pathlib import Path

import typer

from . import __version__
from .capabilities import CapabilityError, load_capabilities, reconcile_capabilities
from .doctor import DoctorError, format_doctor, run_doctor
from .generator import generate_project
from .inspection import InspectionError, format_inspection, inspect_project
from .planning import GenerationError, GenerationPlan, build_generation_plan
from .questions import resolve_questions
from .reconcile import ReconciliationError, reconcile_rag_project
from .recipe import RecipeError, load_recipe

app = typer.Typer(help="Generate and extend AI development environments.")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Show the Metis version."),
) -> None:
    if version:
        typer.echo(f"metis {__version__}")
        raise typer.Exit()


@app.command(name="inspect")
def inspect() -> None:
    """Inspect the current project without modifying it."""
    try:
        report = inspect_project(Path.cwd())
    except (InspectionError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(format_inspection(report))


@app.command(name="doctor")
def doctor() -> None:
    """Diagnose the current Metis project without modifying it."""
    try:
        report = run_doctor(Path.cwd())
    except (DoctorError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(format_doctor(report))
    if report.failures:
        raise typer.Exit(code=1)


@app.command()
def init(
    recipe: str,
    project_name: str | None = typer.Option(None, "--name", "-n"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Directory in which to create the generated project.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the generation plan without writing files."),
) -> None:
    """Generate a project from a built-in recipe."""
    root = repository_root()
    recipe_path = root / "recipes" / recipe / "recipe.yaml"
    schema_path = root / "schema" / "recipe.schema.json"
    try:
        loaded_recipe = load_recipe(recipe_path, schema_path)
        typer.echo("Recipe validated")
        name = project_name or typer.prompt("Project name", default=loaded_recipe.raw.get("project", {}).get("defaultName", "my-rag-app"))
        answers = resolve_questions(loaded_recipe.questions, typer.prompt)
        plan = build_generation_plan(loaded_recipe, name, output or Path.cwd(), answers)
        if dry_run:
            typer.echo(format_generation_plan(plan))
            return
        destination = generate_project(loaded_recipe, name, output or Path.cwd(), answers, plan)
    except (RecipeError, GenerationError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo("Project created")
    typer.echo(f"Project created: ./{destination.name}")
    typer.echo("\nNext:\n\n  cd " + destination.name + "\n  cp .env.example .env\n  docker compose up --build")


def format_generation_plan(plan: GenerationPlan) -> str:
    lines = [
        "Metis generation plan",
        "",
        f"Recipe: {plan.recipe}",
        f"Project: {plan.project_name}",
        f"Destination: {plan.destination}",
        "",
        "Selections:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in plan.selections.items())
    lines.extend(["", "Capabilities:"])
    lines.extend(f"  {capability}" for capability in plan.capabilities)
    lines.extend(["", "Files:"])
    lines.extend(f"  {planned_file.action} {planned_file.path}" for planned_file in plan.files)
    lines.extend(["", "Dry run only. No files were written."])
    return "\n".join(lines)



@app.command()
def add(
    capability_name: str,
) -> None:
    """Add a capability to the current Metis project."""
    root = repository_root()
    capability_root = root / "capabilities"
    schema_path = root / "schema" / "recipe.schema.json"

    try:
        if capability_name == "rag":
            recipe = load_recipe(root / "recipes" / "rag" / "recipe.yaml", schema_path)
            changed = reconcile_rag_project(Path.cwd(), recipe, typer.prompt)
            typer.echo("RAG capability added." if changed else "RAG capability already satisfied.")
            return

        definitions = load_capabilities(capability_root)
        if capability_name in {"rag", "agent"}:
            recipe_path = root / "recipes" / capability_name / "recipe.yaml"
            if not recipe_path.exists():
                raise CapabilityError(f"unsupported capability: {capability_name}")
            recipe = load_recipe(recipe_path, schema_path)
            requested = tuple(recipe.capabilities or ())
        else:
            requested = (capability_name,)

        resolution = reconcile_capabilities(requested, (), definitions)
        if resolution.add:
            typer.echo(f"Capability '{capability_name}' requires: {', '.join(resolution.add)}")
        else:
            typer.echo(f"Capability '{capability_name}' already satisfied.")
    except (CapabilityError, RecipeError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error


if __name__ == "__main__":
    app()