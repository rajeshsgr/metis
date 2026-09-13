from pathlib import Path

from typer.testing import CliRunner

from metis.cli import app


def test_init_rag_generates_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["init", "rag", "--name", "generated"] , input="\n\n\n\n")

    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "generated/app/main.py").exists()
    assert "Project created: ./generated" in result.stdout


def test_init_dry_run_displays_plan_without_creating_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app,
        ["init", "rag", "--name", "preview", "--dry-run"],
        input="\n\n\n\n",
    )

    assert result.exit_code == 0, result.output
    assert "Recipe: rag" in result.output
    assert "Project: preview" in result.output
    assert f"Destination: {tmp_path / 'preview'}" in result.output
    assert "vector_db: qdrant" in result.output
    assert "framework: fastapi" in result.output
    assert "python" in result.output
    assert "CREATE app/main.py" in result.output
    assert "app/main.py.j2" not in result.output
    assert "CREATE .metis/project.yaml" in result.output
    assert "Dry run only. No files were written." in result.output
    assert not (tmp_path / "preview").exists()


def test_init_dry_run_shows_selected_answers_and_does_not_create_output(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "output"
    result = CliRunner().invoke(
        app,
        [
            "init",
            "rag",
            "--output",
            str(output),
            "--name",
            "preview",
            "--dry-run",
        ],
        input="chroma\nanthropic\nhuggingface\nfastapi\n",
    )

    assert result.exit_code == 0, result.output
    assert "vector_db: chroma" in result.output
    assert "llm: anthropic" in result.output
    assert "embedding: huggingface" in result.output
    assert not output.exists()


def test_init_rag_output_creates_project_under_output_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "output" / "nested"
    result = CliRunner().invoke(
        app,
        ["init", "rag", "--output", str(output), "--name", "demo-rag"],
        input="\n\n\n\n",
    )

    assert result.exit_code == 0, result.output
    assert (output / "demo-rag/app/main.py").exists()
    assert not (tmp_path / "demo-rag").exists()


def test_init_refuses_existing_non_empty_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "generated"
    destination.mkdir()
    (destination / "keep.txt").write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(app, ["init", "rag", "--name", "generated"], input="\n\n\n\n")

    assert result.exit_code == 1
    assert "non-empty" in result.output
    assert (destination / "keep.txt").read_text() == "keep"


def test_init_output_refuses_existing_non_empty_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "output"
    destination = output / "generated"
    destination.mkdir(parents=True)
    (destination / "keep.txt").write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["init", "rag", "--output", str(output), "--name", "generated"],
        input="\n\n\n\n",
    )

    assert result.exit_code == 1
    assert "non-empty" in result.output
    assert (destination / "keep.txt").read_text() == "keep"