import json
from pathlib import Path

from app.services.mesh_cleanup import MeshCleanupReport
from app.services.reconstruction import FrameSelection, ReconstructionService


class TestSettings:
    reconstruction_max_frames_per_pass = 90


def cleanup_report() -> MeshCleanupReport:
    return MeshCleanupReport.from_payload(
        {
            "editorReady": True,
            "editorReadyScore": 88,
            "meshObjectCount": 1,
            "boundingBox": {"after": {"maxDimension": 2.4}},
            "normalizedScale": 0.25,
            "triangleCountBefore": 10000,
            "triangleCountAfter": 7000,
            "cleanupWarnings": ["decimated"],
        }
    )


def test_cleanup_reconstructed_model_resolves_texture_and_delegates(tmp_path: Path) -> None:
    obj_path = tmp_path / "shoe.obj"
    mtl_path = tmp_path / "shoe.mtl"
    texture_path = tmp_path / "shoe_texture.jpg"
    obj_path.write_text("mtllib shoe.mtl\no shoe\n", encoding="utf-8")
    mtl_path.write_text("newmtl shoe\nmap_Kd shoe_texture.jpg\n", encoding="utf-8")
    texture_path.write_bytes(b"jpeg")
    model_dir = tmp_path / "model"
    log_path = tmp_path / "pipeline.log"
    service = object.__new__(ReconstructionService)
    service.mesh_cleanup = FakeMeshCleanup()

    report = service._cleanup_reconstructed_model(obj_path, model_dir, log_path)

    assert report.editor_ready is True
    assert service.mesh_cleanup.calls == [
        {
            "source_model": obj_path,
            "output_dir": model_dir,
            "texture_path": texture_path,
            "log_path": log_path,
        }
    ]


def test_reconstruction_quality_report_includes_cleanup_fields(tmp_path: Path) -> None:
    service = object.__new__(ReconstructionService)
    service.settings = TestSettings()
    path = tmp_path / "quality_report.json"
    selections = {
        "side_orbit": FrameSelection(
            selected=[tmp_path / "side_0001.jpg"],
            extracted_count=3,
            rejected_by_reason={"invalid": 0, "dark": 1},
            average_brightness=120,
            average_sharpness=360,
        )
    }

    service._write_quality_report(path, selections, cleanup_report())

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["editorReady"] is True
    assert payload["editorReadyScore"] == 88
    assert payload["cleanupWarnings"] == ["decimated"]


class FakeMeshCleanup:
    def __init__(self) -> None:
        self.calls = []

    def cleanup(self, source_model, output_dir, *, texture_path=None, log_path=None):
        self.calls.append(
            {
                "source_model": source_model,
                "output_dir": output_dir,
                "texture_path": texture_path,
                "log_path": log_path,
            }
        )
        return cleanup_report()
