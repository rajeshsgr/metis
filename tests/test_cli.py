from pathlib import Path

from typer.testing import CliRunner

from metis.cli import app


def test_init_rag_generates_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["init", "rag", "--name", "generated"] , input="\n\n\n\n")

    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "generated/app/main.py").exists()
    assert "Project created: ./generated" in result.stdout


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