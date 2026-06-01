import pytest
from fastapi import HTTPException, status

from app.services.mesh_cleanup import MeshCleanupReport
from app.services.model_imports import ModelImportService, StagedModel, UploadedModelFile


class TestSettings:
    max_upload_size_mb = 1


@pytest.fixture
def import_service() -> ModelImportService:
    service = object.__new__(ModelImportService)
    service.settings = TestSettings()
    return service


def upload(name: str, data: bytes = b"data") -> UploadedModelFile:
    return UploadedModelFile(file_name=name, content_type=None, data=data)


def cleanup_report() -> MeshCleanupReport:
    return MeshCleanupReport.from_payload(
        {
            "editorReady": True,
            "editorReadyScore": 95,
            "meshObjectCount": 1,
            "boundingBox": {"after": {"maxDimension": 2.4}},
            "normalizedScale": 0.5,
            "triangleCountBefore": 2000,
            "triangleCountAfter": 1800,
            "cleanupWarnings": [],
        }
    )


def test_glb_import_rejects_extra_files(import_service: ModelImportService) -> None:
    with pytest.raises(HTTPException) as exc:
        import_service._validate_inputs(
            "glb",
            model_file=upload("shoe.glb"),
            mtl_file=upload("shoe.mtl"),
            texture_file=None,
            package_file=None,
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_obj_zip_rejects_path_traversal(import_service: ModelImportService) -> None:
    with pytest.raises(HTTPException) as exc:
        import_service._safe_zip_path("../shoe.obj")

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsafe ZIP path" in exc.value.detail


def test_total_upload_size_uses_configured_limit(import_service: ModelImportService) -> None:
    oversized = b"x" * (TestSettings.max_upload_size_mb * 1024 * 1024 + 1)

    with pytest.raises(HTTPException) as exc:
        import_service._validate_total_upload_size([upload("shoe.glb", oversized)])

    assert exc.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE


def test_cleanup_staged_model_delegates_to_mesh_cleanup(tmp_path) -> None:
    service = object.__new__(ModelImportService)
    service.mesh_cleanup = FakeMeshCleanup()
    staged = StagedModel(
        input_path=tmp_path / "source.obj",
        texture_path=tmp_path / "source_texture.png",
        source_files=["source.obj"],
    )
    model_dir = tmp_path / "model"

    report = service._cleanup_staged_model(staged, model_dir)

    assert report.editor_ready is True
    assert service.mesh_cleanup.calls == [
        {
            "source_model": staged.input_path,
            "output_dir": model_dir,
            "texture_path": staged.texture_path,
            "log_path": model_dir / "import.log",
        }
    ]


def test_import_quality_report_includes_cleanup_fields(tmp_path) -> None:
    service = object.__new__(ModelImportService)
    path = tmp_path / "quality_report.json"

    service._write_quality_report(
        path,
        "Imported shoe",
        "obj",
        ["source.obj"],
        cleanup_report(),
    )

    payload = path.read_text(encoding="utf-8")
    assert '"status": "imported"' in payload
    assert '"editorReady": true' in payload
    assert '"editorReadyScore": 95' in payload


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
