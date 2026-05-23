from __future__ import annotations

import io
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ModelAsset, ScanSession, ScanSource, ScanStatus, User
from app.schemas.scan import ScanMetadata
from app.services.blender_service import BlenderService
from app.services.command_runner import CommandRunner
from app.services.file_helpers import write_json
from app.services.model_assets import ModelAssetFiles, ModelAssetService
from app.services.placeholders import PLACEHOLDER_PNG
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
        self.blender = BlenderService()
        self.runner = CommandRunner()

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
    ) -> ModelAsset:
        display_name = name.strip()
        if not display_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Model name is required.")

        normalized_format = import_format.strip().lower()
        if normalized_format not in SUPPORTED_MODEL_FORMATS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Format must be 'glb' or 'obj'.")

        self._validate_total_upload_size([model_file, mtl_file, texture_file, package_file])
        self._validate_inputs(normalized_format, model_file, mtl_file, texture_file, package_file)

        scan_session = self._create_import_session(user, display_name, metadata)
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
            self._write_import_script(work_dir / "import_model.py")
            self._run_blender_import(work_dir / "import_model.py", staged, model_dir)
            self._ensure_canonical_files(model_dir, staged.texture_path)
            metadata_path = model_dir / "metadata.json"
            metadata_path.write_bytes(scan_metadata_bytes(metadata))
            quality_report_path = model_dir / "quality_report.json"
            self._write_quality_report(
                quality_report_path,
                display_name,
                normalized_format,
                staged.source_files,
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

    def _create_import_session(self, user: User, name: str, metadata: ScanMetadata) -> ScanSession:
        scan_session = ScanSession(
            user_id=user.id,
            status=ScanStatus.EXPORTING,
            source_type=ScanSource.IMPORT,
            import_name=name,
        )
        self.db.add(scan_session)
        self.db.flush()
        scan_session.web_design_url = self.scan_service.web_design_url(scan_session.id)
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

    def _run_blender_import(self, script_path: Path, staged: StagedModel, model_dir: Path) -> None:
        command = [
            self.blender.require_available(),
            "--background",
            "--python",
            str(script_path),
            "--",
            str(staged.input_path),
            str(model_dir),
            str(staged.texture_path or ""),
        ]
        result = self.runner.run(
            command,
            log_path=model_dir / "import.log",
            cwd=staged.input_path.parent,
            timeout=self.settings.reconstruction_command_timeout_seconds,
        )
        if not result.ok:
            message = result.stderr.strip() or result.stdout.strip() or "Blender import failed."
            raise RuntimeError(message[-1200:])

    def _write_import_script(self, path: Path) -> None:
        path.write_text(
            r'''
import sys
import traceback
from pathlib import Path

import bpy


def patch_numpy_compat():
    try:
        import numpy as np
    except Exception as exc:
        raise RuntimeError("Blender GLB importer requires numpy in the backend image.") from exc

    aliases = {
        "bool": bool,
        "int": int,
        "float": float,
        "complex": complex,
        "object": object,
        "str": str,
    }
    for name, value in aliases.items():
        if name not in np.__dict__:
            setattr(np, name, value)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_model(input_path: Path):
    suffix = input_path.suffix.lower()
    if suffix == ".glb":
        patch_numpy_compat()
        bpy.ops.import_scene.gltf(filepath=str(input_path))
        return
    if suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(input_path))
        else:
            bpy.ops.import_scene.obj(filepath=str(input_path))
        return
    raise RuntimeError(f"Unsupported model extension: {suffix}")


def export_obj(path: Path):
    if hasattr(bpy.ops.wm, "obj_export"):
        bpy.ops.wm.obj_export(filepath=str(path), export_materials=True)
    else:
        bpy.ops.export_scene.obj(filepath=str(path), use_materials=True, path_mode="COPY")


def save_texture(texture_path: str, output_path: Path):
    if not texture_path:
        return
    image = bpy.data.images.load(texture_path)
    image.filepath_raw = str(output_path)
    image.file_format = "PNG"
    image.save()


try:
    argv = sys.argv[sys.argv.index("--") + 1:]
    input_path = Path(argv[0])
    output_dir = Path(argv[1])
    texture_path = argv[2] if len(argv) > 2 else ""
    output_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    import_model(input_path)
    mesh_objects = [item for item in bpy.context.scene.objects if item.type == "MESH"]
    if not mesh_objects:
        raise RuntimeError("Imported model contains no mesh objects.")

    bpy.ops.export_scene.gltf(filepath=str(output_dir / "shoe_preview.glb"), export_format="GLB")
    export_obj(output_dir / "shoe.obj")
    save_texture(texture_path, output_dir / "shoe_texture.png")
except Exception:
    traceback.print_exc()
    sys.exit(1)
'''.lstrip(),
            encoding="utf-8",
        )

    def _ensure_canonical_files(self, model_dir: Path, texture_path: Path | None) -> None:
        for required in ["shoe_preview.glb", "shoe.obj"]:
            if not (model_dir / required).is_file():
                raise RuntimeError(f"Blender did not create {required}.")
        if not (model_dir / "shoe.mtl").is_file():
            (model_dir / "shoe.mtl").write_text(
                "newmtl imported_material\nKd 1.000000 1.000000 1.000000\nmap_Kd shoe_texture.png\n",
                encoding="utf-8",
            )
        if not (model_dir / "shoe_texture.png").is_file():
            if texture_path and texture_path.suffix.lower() == ".png":
                shutil.copyfile(texture_path, model_dir / "shoe_texture.png")
            else:
                (model_dir / "shoe_texture.png").write_bytes(PLACEHOLDER_PNG)

    def _write_quality_report(
        self,
        path: Path,
        name: str,
        import_format: str,
        source_files: list[str],
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
