import pytest
from fastapi import HTTPException, status

from app.services.model_imports import ModelImportService, UploadedModelFile


class TestSettings:
    max_upload_size_mb = 1


@pytest.fixture
def import_service() -> ModelImportService:
    service = object.__new__(ModelImportService)
    service.settings = TestSettings()
    return service


def upload(name: str, data: bytes = b"data") -> UploadedModelFile:
    return UploadedModelFile(file_name=name, content_type=None, data=data)


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
