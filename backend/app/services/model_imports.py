from __future__ import annotations

import io
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ModelAsset, ProjectSourceType, ProjectStatus, ScanSession, ScanSource, ScanStatus, User
from app.schemas.scan import ScanMetadata
from app.services.file_helpers import write_json
from app.services.mesh_cleanup import MeshCleanupReport, MeshCleanupService
from app.services.model_assets import ModelAssetFiles, ModelAssetService
from app.services.scan_metadata import scan_metadata_bytes
from app.services.scan_sessions import ScanSessionService
from app.services.storage import get_storage_service


SUPPORTED_MODEL_FORMATS = {"glb", "obj"}
OBJ_TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
OBJ_PACKAGE_EXTENSIONS = {".obj", ".mtl", ".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class UploadedModelFile:
    file_name: str | None
    content_type: str | None
    data: bytes


@dataclass(frozen=True)
class StagedModel:
    input_path: Path
    texture_path: Path | None
    source_files: list[str]


class ModelImportService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.storage = get_storage_service()
        self.scan_service = ScanSessionService(db)
        self.asset_service = ModelAssetService(db)
        self.mesh_cleanup = MeshCleanupService()

    def import_model(
        self,
        user: User,
        name: str,
        import_format: str,
        metadata: ScanMetadata,
        model_file: UploadedModelFile | None = None,
        mtl_file: UploadedModelFile | None = None,
        texture_file: UploadedModelFile | None = None,
        package_file: UploadedModelFile | None = None,
        project_id: str | None = None,
    ) -> ModelAsset:
        display_name = name.strip()
        if not display_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Model name is required.")

        normalized_format = import_format.strip().lower()
        if normalized_format not in SUPPORTED_MODEL_FORMATS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Format must be 'glb' or 'obj'.")

        self._validate_total_upload_size([model_file, mtl_file, texture_file, package_file])
        self._validate_inputs(normalized_format, model_file, mtl_file, texture_file, package_file)

        scan_session = self._create_import_session(user, display_name, metadata, normalized_format, project_id)
        work_dir = self.settings.resolved_storage_root / "imports" / scan_session.id
        model_dir = self.settings.resolved_storage_root / "models" / scan_session.id

        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
            if model_dir.exists():
                shutil.rmtree(model_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
            model_dir.mkdir(parents=True, exist_ok=True)

            staged = (
                self._stage_glb(work_dir, model_file)
                if normalized_format == "glb"
                else self._stage_obj(work_dir, model_file, mtl_file, texture_file, package_file)
            )
            cleanup_report = self._cleanup_staged_model(staged, model_dir)
            metadata_path = model_dir / "metadata.json"
            metadata_path.write_bytes(scan_metadata_bytes(metadata))
            quality_report_path = model_dir / "quality_report.json"
            self._write_quality_report(
                quality_report_path,
                display_name,
                normalized_format,
                staged.source_files,
                cleanup_report,
            )
            obj_package_path = model_dir / "shoe_obj_package.zip"
            self._zip_obj_package(model_dir, obj_package_path)
            asset = self.asset_service.create_from_files(
                scan_session.id,
                ModelAssetFiles(
                    glb=model_dir / "shoe_preview.glb",
                    obj=model_dir / "shoe.obj",
                    mtl=model_dir / "shoe.mtl",
                    texture=model_dir / "shoe_texture.png",
                    metadata=metadata_path,
                    quality_report=quality_report_path,
                    obj_package_zip=obj_package_path,
                ),
                source_type=(
                    ProjectSourceType.UPLOADED_GLB
                    if normalized_format == "glb"
                    else ProjectSourceType.UPLOADED_OBJ
                ),
            )
            self.scan_service.set_status(scan_session.id, ScanStatus.COMPLETED)
            return asset
        except HTTPException:
            self.scan_service.set_status(scan_session.id, ScanStatus.FAILED, "Model import failed.")
            raise
        except Exception as exc:
            message = str(exc) or "Model import failed."
            self.scan_service.set_status(scan_session.id, ScanStatus.FAILED, message[:2000])
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    def _create_import_session(
        self,
        user: User,
        name: str,
        metadata: ScanMetadata,
        normalized_format: str,
        project_id: str | None,
    ) -> ScanSession:
        project = self.scan_service._project_for_scan(
            user=user,
            project_id=project_id,
            fallback_name=name,
            source_type=(
                ProjectSourceType.UPLOADED_GLB
                if normalized_format == "glb"
                else ProjectSourceType.UPLOADED_OBJ
            ),
        )
        project.status = ProjectStatus.PROCESSING
        scan_session = ScanSession(
            user_id=user.id,
            project_id=project.id,
            status=ScanStatus.EXPORTING,
            source_type=ScanSource.IMPORT,
            import_name=name,
        )
        self.db.add(scan_session)
        self.db.flush()
        scan_session.web_design_url = self.scan_service.web_design_url(scan_session.id, project.id)
        metadata_object = self.storage.put_bytes(
            f"imports/{scan_session.id}/metadata.json",
            scan_metadata_bytes(metadata),
            "application/json",
        )
        scan_session.metadata_path = metadata_object.key
        scan_session.metadata_size_bytes = metadata_object.size_bytes
        scan_session.metadata_content_type = metadata_object.content_type
        scan_session.metadata_checksum = metadata_object.checksum
        self.db.commit()
        self.db.refresh(scan_session)
        return scan_session

    def _validate_total_upload_size(self, files: list[UploadedModelFile | None]) -> None:
        total_bytes = sum(len(file.data) for file in files if file)
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Uploaded model exceeds {self.settings.max_upload_size_mb} MB.",
            )

    def _validate_inputs(
        self,
        import_format: str,
        model_file: UploadedModelFile | None,
        mtl_file: UploadedModelFile | None,
        texture_file: UploadedModelFile | None,
        package_file: UploadedModelFile | None,
    ) -> None:
        if import_format == "glb":
            if not model_file or package_file or mtl_file or texture_file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GLB import requires only the 'model' .glb file.",
                )
            self._validate_file(model_file, {".glb"}, "model")
            return

        if package_file:
            if model_file or mtl_file or texture_file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OBJ ZIP import uses 'package' only; do not mix separate files.",
                )
            self._validate_file(package_file, {".zip"}, "package")
            return

        if not model_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OBJ import requires a .obj 'model' file or a .zip 'package'.",
            )
        self._validate_file(model_file, {".obj"}, "model")
        if mtl_file:
            self._validate_file(mtl_file, {".mtl"}, "mtl")
        if texture_file:
            self._validate_file(texture_file, OBJ_TEXTURE_EXTENSIONS, "texture")

    def _validate_file(self, upload: UploadedModelFile, allowed_extensions: set[str], label: str) -> None:
        suffix = Path(upload.file_name or "").suffix.lower()
        if suffix not in allowed_extensions:
            allowed = ", ".join(sorted(allowed_extensions))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {label} file. Expected one of: {allowed}.",
            )
        if not upload.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded {label} file is empty.",
            )

    def _stage_glb(self, work_dir: Path, model_file: UploadedModelFile | None) -> StagedModel:
        if not model_file:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GLB model file is required.")
        input_path = work_dir / "source.glb"
        input_path.write_bytes(model_file.data)
        return StagedModel(input_path=input_path, texture_path=None, source_files=[model_file.file_name or "model.glb"])

    def _stage_obj(
        self,
        work_dir: Path,
        model_file: UploadedModelFile | None,
        mtl_file: UploadedModelFile | None,
        texture_file: UploadedModelFile | None,
        package_file: UploadedModelFile | None,
    ) -> StagedModel:
        if package_file:
            return self._stage_obj_zip(work_dir, package_file)

        if not model_file:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OBJ model file is required.")
        obj_path = self._write_uploaded_file(work_dir, model_file, "source.obj")
        source_files = [model_file.file_name or "model.obj"]
        texture_path = None
        if mtl_file:
            self._write_uploaded_file(work_dir, mtl_file, "source.mtl")
            source_files.append(mtl_file.file_name or "model.mtl")
        if texture_file:
            texture_path = self._write_uploaded_file(work_dir, texture_file, "source_texture.png")
            source_files.append(texture_file.file_name or "texture")
        return StagedModel(input_path=obj_path, texture_path=texture_path, source_files=source_files)

    def _stage_obj_zip(self, work_dir: Path, package_file: UploadedModelFile) -> StagedModel:
        source_files: list[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(package_file.data)) as archive:
                total_uncompressed = 0
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    safe_path = self._safe_zip_path(item.filename)
                    if not safe_path:
                        continue
                    if safe_path.suffix.lower() not in OBJ_PACKAGE_EXTENSIONS:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unsupported file in OBJ package: {safe_path.name}.",
                        )
                    total_uncompressed += item.file_size
                    max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
                    if total_uncompressed > max_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"OBJ package exceeds {self.settings.max_upload_size_mb} MB after extraction.",
                        )
                    target = (work_dir / Path(*safe_path.parts)).resolve()
                    if work_dir.resolve() not in target.parents:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsafe ZIP path.")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(item))
                    source_files.append(safe_path.as_posix())
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OBJ ZIP package.") from exc

        obj_paths = sorted(work_dir.rglob("*.obj"))
        if len(obj_paths) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OBJ ZIP package must contain exactly one .obj file.",
            )
        texture_paths = sorted(
            path for path in work_dir.rglob("*") if path.suffix.lower() in OBJ_TEXTURE_EXTENSIONS
        )
        return StagedModel(
            input_path=obj_paths[0],
            texture_path=texture_paths[0] if texture_paths else None,
            source_files=source_files,
        )

    def _safe_zip_path(self, raw_name: str) -> PurePosixPath | None:
        path = PurePosixPath(raw_name)
        if path.is_absolute() or ".." in path.parts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsafe ZIP path.")
        if not path.name or path.name.startswith(".") or "__MACOSX" in path.parts:
            return None
        return path

    def _write_uploaded_file(self, work_dir: Path, upload: UploadedModelFile, fallback_name: str) -> Path:
        filename = Path(upload.file_name or fallback_name).name or fallback_name
        target = work_dir / filename
        target.write_bytes(upload.data)
        return target

    def _cleanup_staged_model(self, staged: StagedModel, model_dir: Path) -> MeshCleanupReport:
        return self.mesh_cleanup.cleanup(
            staged.input_path,
            model_dir,
            texture_path=staged.texture_path,
            log_path=model_dir / "import.log",
        )

    def _write_quality_report(
        self,
        path: Path,
        name: str,
        import_format: str,
        source_files: list[str],
        cleanup_report: MeshCleanupReport,
    ) -> None:
        write_json(
            path,
            {
                "overallScore": 100,
                "status": "imported",
                "importName": name,
                "sourceFormat": import_format,
                "sourceFiles": source_files,
                "textureConfidence": "imported",
                "geometryConfidence": "imported",
                "scaleConfidence": "manual",
                "coverageScore": 100,
                "warnings": ["Model was uploaded directly; scan quality metrics are not available."],
                "recommendation": "Use for visual shoe customization review.",
                **cleanup_report.to_quality_fields(),
            },
        )

    def _zip_obj_package(self, model_dir: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in [
                "shoe.obj",
                "shoe.mtl",
                "shoe_texture.png",
                "metadata.json",
                "quality_report.json",
            ]:
                archive.write(model_dir / name, name)
