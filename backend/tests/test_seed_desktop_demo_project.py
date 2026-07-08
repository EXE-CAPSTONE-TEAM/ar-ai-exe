from pathlib import Path

import pytest

from app.scripts.seed_desktop_demo_project import validate_demo_model_path


def test_validate_demo_model_path_accepts_existing_glb(tmp_path: Path) -> None:
    model_path = tmp_path / "shoe.glb"
    model_path.write_bytes(b"glb")

    assert validate_demo_model_path(model_path) == model_path.resolve()


def test_validate_demo_model_path_rejects_unsupported_extension(tmp_path: Path) -> None:
    model_path = tmp_path / "shoe.txt"
    model_path.write_text("not a model", encoding="utf-8")

    with pytest.raises(ValueError, match="Demo model must use one of these extensions"):
        validate_demo_model_path(model_path)
