from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.services.command_runner import CommandResult
from app.services.mesh_sculpt_service import MeshSculptService, SculptResult


def test_parse_metric() -> None:
    service = MeshSculptService()
    stdout = "some output\nHIGH_POLY_FACES=12345\nother output\nLOW_POLY_FACES=987\n"
    assert service._parse_metric(stdout, "HIGH_POLY_FACES") == 12345
    assert service._parse_metric(stdout, "LOW_POLY_FACES") == 987
    assert service._parse_metric(stdout, "NON_EXISTENT") == 0


def test_sculpt_and_bake_success(tmp_path: Path) -> None:
    settings = Settings()
    service = MeshSculptService(settings)

    # Mock CommandRunner
    mock_runner = MagicMock()
    mock_result = CommandResult(
        command=["blender", "--background"],
        return_code=0,
        stdout="HIGH_POLY_FACES=50000\nLOW_POLY_FACES=4000\nSCULPT_BAKE_COMPLETE",
        stderr="",
    )
    mock_runner.run.return_value = mock_result
    service.runner = mock_runner

    # Mock BlenderService
    mock_blender = MagicMock()
    mock_blender.sculpt_bake_command.return_value = ["blender", "--background"]
    service.blender = mock_blender

    # Setup inputs
    input_mesh = tmp_path / "raw.obj"
    input_mesh.write_text("v 0 0 0", encoding="utf-8")
    output_dir = tmp_path / "output"
    log_path = tmp_path / "test.log"

    # Pre-create output files because validate_outputs checks for their existence
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "low_poly.obj").write_text("low poly obj", encoding="utf-8")
    (output_dir / "low_poly.glb").write_bytes(b"low poly glb")
    (output_dir / "normal_map.png").write_bytes(b"normal map png")
    (output_dir / "diffuse_texture.png").write_bytes(b"diffuse texture png")

    result = service.sculpt_and_bake(input_mesh, output_dir, log_path)

    # Verify CommandRunner calls
    mock_runner.run.assert_called_once()
    mock_blender.sculpt_bake_command.assert_called_once_with(
        script_path=output_dir / "auto_sculpt_bake.py",
        input_mesh_path=input_mesh,
        output_dir=output_dir,
        voxel_size=settings.sculpt_voxel_size,
        smooth_iterations=settings.sculpt_smooth_iterations,
        smooth_factor=settings.sculpt_smooth_factor,
        decimate_ratio=settings.sculpt_decimate_ratio,
        normal_map_size=settings.sculpt_normal_map_size,
        texture_size=settings.sculpt_texture_size,
    )

    # Verify script content compile check
    script_path = output_dir / "auto_sculpt_bake.py"
    assert script_path.exists()
    # Compile checking Python script to ensure syntax is valid
    compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec")

    # Verify result fields
    assert isinstance(result, SculptResult)
    assert result.low_poly_obj == output_dir / "low_poly.obj"
    assert result.low_poly_glb == output_dir / "low_poly.glb"
    assert result.normal_map == output_dir / "normal_map.png"
    assert result.diffuse_texture == output_dir / "diffuse_texture.png"
    assert result.high_poly_face_count == 50000
    assert result.low_poly_face_count == 4000
    assert result.reduction_ratio == pytest.approx(0.08)


def test_sculpt_and_bake_blender_failure(tmp_path: Path) -> None:
    service = MeshSculptService()

    # Mock CommandRunner failure
    mock_runner = MagicMock()
    mock_result = CommandResult(
        command=["blender", "--background"],
        return_code=1,
        stdout="",
        stderr="MemoryError: out of memory",
    )
    mock_runner.run.return_value = mock_result
    service.runner = mock_runner

    mock_blender = MagicMock()
    mock_blender.sculpt_bake_command.return_value = ["blender"]
    service.blender = mock_blender

    input_mesh = tmp_path / "raw.obj"
    output_dir = tmp_path / "output"
    log_path = tmp_path / "test.log"

    with pytest.raises(RuntimeError) as exc:
        service.sculpt_and_bake(input_mesh, output_dir, log_path)

    assert "Auto-sculpt & bake failed: MemoryError: out of memory" in str(exc.value)


def test_sculpt_and_bake_missing_outputs(tmp_path: Path) -> None:
    service = MeshSculptService()

    mock_runner = MagicMock()
    mock_result = CommandResult(
        command=["blender", "--background"],
        return_code=0,
        stdout="HIGH_POLY_FACES=50000\nLOW_POLY_FACES=4000",
        stderr="",
    )
    mock_runner.run.return_value = mock_result
    service.runner = mock_runner

    mock_blender = MagicMock()
    mock_blender.sculpt_bake_command.return_value = ["blender"]
    service.blender = mock_blender

    input_mesh = tmp_path / "raw.obj"
    output_dir = tmp_path / "output"
    log_path = tmp_path / "test.log"

    # Don't pre-create output files, which should trigger a validation error
    with pytest.raises(RuntimeError) as exc:
        service.sculpt_and_bake(input_mesh, output_dir, log_path)

    assert "Auto-sculpt did not produce low_poly.obj." in str(exc.value)
