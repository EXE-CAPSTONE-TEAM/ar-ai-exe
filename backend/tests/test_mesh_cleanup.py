import json
from pathlib import Path

from app.services.command_runner import CommandResult
from app.services.mesh_cleanup import MeshCleanupOptions, MeshCleanupReport, MeshCleanupService


def cleanup_report_payload() -> dict:
    return {
        "editorReady": True,
        "editorReadyScore": 92,
        "meshObjectCount": 2,
        "boundingBox": {
            "before": {"maxDimension": 8.0},
            "after": {"maxDimension": 2.4},
        },
        "normalizedScale": 0.3,
        "triangleCountBefore": 12000,
        "triangleCountAfter": 8000,
        "cleanupWarnings": ["minor non-mesh objects removed"],
    }


def cleanup_report() -> MeshCleanupReport:
    return MeshCleanupReport.from_payload(cleanup_report_payload())


def test_cleanup_report_maps_to_quality_fields() -> None:
    report = cleanup_report()

    assert report.to_quality_fields() == {
        "editorReady": True,
        "editorReadyScore": 92,
        "meshObjectCount": 2,
        "boundingBox": {
            "before": {"maxDimension": 8.0},
            "after": {"maxDimension": 2.4},
        },
        "normalizedScale": 0.3,
        "triangleCountBefore": 12000,
        "triangleCountAfter": 8000,
        "cleanupWarnings": ["minor non-mesh objects removed"],
    }


def test_cleanup_runs_blender_background_and_ensures_canonical_files(tmp_path: Path) -> None:
    source_model = tmp_path / "source.obj"
    source_model.write_text("o shoe\n", encoding="utf-8")
    output_dir = tmp_path / "out"
    runner = FakeRunner(cleanup_report_payload())

    service = MeshCleanupService(
        blender=FakeBlender(),
        runner=runner,
        options=MeshCleanupOptions(
            target_max_dimension=2.4,
            decimate_triangle_threshold=1000,
            decimate_ratio=0.5,
        ),
    )

    report = service.cleanup(source_model, output_dir)

    assert len(runner.command) >= 3
    assert runner.command[0] == "blender"
    assert runner.command[1] == "--background"
    assert runner.command[2] == "--python"
    assert runner.command[-5:] == [
        str(source_model),
        str(output_dir),
        str(output_dir / "_mesh_cleanup" / "mesh_cleanup_report.json"),
        str(output_dir / "_mesh_cleanup" / "mesh_cleanup_options.json"),
        "",
    ]
    assert (output_dir / "shoe_preview.glb").read_bytes() == b"glb"
    assert (output_dir / "shoe.obj").read_text(encoding="utf-8") == "o shoe\n"
    assert "map_Kd shoe_texture.png" in (output_dir / "shoe.mtl").read_text(encoding="utf-8")
    assert (output_dir / "shoe_texture.png").read_bytes()
    assert report.editor_ready is True
    assert report.editor_ready_score == 92


def test_cleanup_script_compiles_and_contains_editor_ready_steps(tmp_path: Path) -> None:
    service = object.__new__(MeshCleanupService)
    script_path = tmp_path / "editor_ready_cleanup.py"

    service._write_cleanup_script(script_path)
    script = script_path.read_text(encoding="utf-8")

    compile(script, str(script_path), "exec")
    assert "def normalize_scene" in script
    assert "def clean_mesh_geometry" in script
    assert "def apply_decimation" in script
    assert "def save_texture" in script
    assert "editorReadyScore" in script


class FakeBlender:
    def require_available(self) -> str:
        return "blender"


class FakeRunner:
    def __init__(self, report_payload: dict):
        self.report_payload = report_payload
        self.command: list[str] = []

    def run(
        self,
        command: list[str],
        log_path: Path | None = None,
        cwd: Path | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        self.command = command
        output_dir = Path(command[-4])
        report_path = Path(command[-3])
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        (output_dir / "shoe_preview.glb").write_bytes(b"glb")
        (output_dir / "shoe.obj").write_text("o shoe\n", encoding="utf-8")
        report_path.write_text(json.dumps(self.report_payload), encoding="utf-8")
        return CommandResult(command=command, return_code=0, stdout="", stderr="")
