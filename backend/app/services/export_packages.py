import json
import shutil
import zipfile
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Design, DesignStatus, ExportPackage, ModelAsset, User
from app.schemas.export import ExportPackageResponse
from app.services.decal_baker import DecalBakeService
from app.services.design_assets import DesignAssetService
from app.services.designs import DesignService
from app.services.model_assets import ModelAssetService
from app.services.placeholders import PLACEHOLDER_PNG
from app.services.storage import get_storage_service


class ExportPackageService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.storage = get_storage_service()

    def create(self, design: Design) -> ExportPackage:
        asset = self.db.get(ModelAsset, design.model_asset_id)
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model asset not found.")

        export_package = ExportPackage(
            design_id=design.id,
            glb_path="",
            obj_path="",
            mtl_path="",
            texture_path="",
            preview_images_path="",
            production_notes_path="",
            zip_path="",
        )
        self.db.add(export_package)
        self.db.flush()

        export_dir = self._export_folder(export_package.id)
        if export_dir.exists():
            shutil.rmtree(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        glb_path = export_dir / "final_shoe.glb"
        obj_path = export_dir / "final_shoe.obj"
        mtl_path = export_dir / "final_shoe.mtl"
        texture_path = export_dir / "final_texture.png"
        design_config_path = export_dir / "design_config.json"
        measurement_info_path = export_dir / "measurement_info.json"
        production_notes_path = export_dir / "production_notes.json"
        preview_dir = export_dir

        model_service = ModelAssetService(self.db)
        design_service = DesignService(self.db)
        design_config = design_service.read_config(design)
        glb_path.write_bytes(model_service.file_bytes(asset, "glb"))
        obj_path.write_bytes(model_service.file_bytes(asset, "obj"))
        mtl_path.write_bytes(model_service.file_bytes(asset, "mtl"))
        texture_path.write_bytes(model_service.file_bytes(asset, "texture"))
        design_config_path.write_text(
            json.dumps(design_config, indent=2),
            encoding="utf-8",
        )
        self._write_measurements(asset, measurement_info_path)
        self._write_previews(preview_dir)
        asset_service = DesignAssetService(self.db)
        decals_baked = DecalBakeService(
            asset_resolver=lambda asset_id: asset_service.image_payload_for_user_id(
                asset_id,
                design.user_id,
            )
        ).bake(glb_path, export_dir, design_config)
        self._write_production_notes(design, production_notes_path, decals_baked)

        zip_path = export_dir / f"{export_package.id}.zip"
        self._zip_export(export_dir, zip_path)

        glb_object = self.storage.put_bytes(
            f"exports/{export_package.id}/final_shoe.glb",
            glb_path.read_bytes(),
            "model/gltf-binary",
        )
        obj_object = self.storage.put_bytes(
            f"exports/{export_package.id}/final_shoe.obj",
            obj_path.read_bytes(),
            "text/plain",
        )
        mtl_object = self.storage.put_bytes(
            f"exports/{export_package.id}/final_shoe.mtl",
            mtl_path.read_bytes(),
            "text/plain",
        )
        texture_object = self.storage.put_bytes(
            f"exports/{export_package.id}/final_texture.png",
            texture_path.read_bytes(),
            "image/png",
        )
        notes_object = self.storage.put_bytes(
            f"exports/{export_package.id}/production_notes.json",
            production_notes_path.read_bytes(),
            "application/json",
        )
        zip_object = self.storage.put_bytes(
            f"exports/{export_package.id}/{export_package.id}.zip",
            zip_path.read_bytes(),
            "application/zip",
        )

        export_package.glb_path = glb_object.key
        export_package.obj_path = obj_object.key
        export_package.mtl_path = mtl_object.key
        export_package.texture_path = texture_object.key
        export_package.preview_images_path = f"exports/{export_package.id}/"
        export_package.production_notes_path = notes_object.key
        export_package.zip_path = zip_object.key
        export_package.zip_size_bytes = zip_object.size_bytes
        export_package.zip_content_type = zip_object.content_type
        export_package.zip_checksum = zip_object.checksum
        design.status = DesignStatus.EXPORTED

        self.db.commit()
        self.db.refresh(export_package)
        return export_package

    def get(self, export_id: str) -> ExportPackage:
        export_package = self.db.get(ExportPackage, export_id)
        if not export_package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export package not found.",
            )
        return export_package

    def get_for_user(self, export_id: str, user: User) -> ExportPackage:
        export_package = self.get(export_id)
        if export_package.design.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export package not found.",
            )
        return export_package

    def response(self, export_package: ExportPackage) -> ExportPackageResponse:
        return ExportPackageResponse(
            id=export_package.id,
            designId=export_package.design_id,
            status=export_package.status,
            downloadUrl=f"/api/exports/{export_package.id}/download",
            files=[
                "final_shoe.glb",
                "final_shoe.obj",
                "final_shoe.mtl",
                "final_texture.png",
                "stickers/*",
                "preview_front.png",
                "preview_side.png",
                "preview_top.png",
                "preview_back.png",
                "design_config.json",
                "measurement_info.json",
                "production_notes.json",
            ],
            createdAt=export_package.created_at,
        )

    def zip_bytes(self, export_package: ExportPackage) -> bytes:
        if self.storage.exists(export_package.zip_path):
            return self.storage.get_bytes(export_package.zip_path)
        return Path(export_package.zip_path).read_bytes()

    def _export_folder(self, export_id: str) -> Path:
        return self.settings.resolved_storage_root / "exports" / export_id

    def _read_scan_metadata(self, asset: ModelAsset) -> dict:
        metadata_key = asset.scan_session.metadata_path or ""
        if metadata_key and self.storage.exists(metadata_key):
            return json.loads(self.storage.get_bytes(metadata_key).decode("utf-8"))
        metadata_path = Path(metadata_key)
        if metadata_path.exists():
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        return {}

    def _write_measurements(self, asset: ModelAsset, path: Path) -> None:
        metadata = self._read_scan_metadata(asset)
        self._write_json(
            path,
            {
                "shoe": metadata.get("shoe", {}),
                "measurements": metadata.get("measurements", {}),
                "scanSetup": metadata.get("scanSetup", {}),
            },
        )

    def _write_previews(self, preview_dir: Path) -> None:
        preview_dir.mkdir(parents=True, exist_ok=True)
        for name in ["front", "side", "top", "back"]:
            preview_path = preview_dir / f"preview_{name}.png"
            preview_path.write_bytes(PLACEHOLDER_PNG)
            self.storage.put_bytes(
                f"exports/{preview_dir.name}/preview_{name}.png",
                PLACEHOLDER_PNG,
                "image/png",
            )

    def _write_production_notes(self, design: Design, path: Path, decals_baked: bool = False) -> None:
        metadata = self._read_scan_metadata(design.model_asset)
        design_config = DesignService(self.db).read_config(design)
        shoe = metadata.get("shoe", {})
        measurements = metadata.get("measurements", {})
        self._write_json(
            path,
            {
                "orderType": "visual_design_package",
                "shoe": {
                    "size": f"{shoe.get('sizeSystem', '')} {shoe.get('size', '')}".strip(),
                    "side": shoe.get("side"),
                    "lengthCm": measurements.get("lengthCm"),
                    "widthCm": measurements.get("widthCm"),
                    "material": shoe.get("material"),
                },
                "customization": {
                    "summary": self._summary(design_config),
                    "targetAreas": ["manual_reference"],
                    "colorCodes": [design_config.get("baseColor", "#ffffff")],
                    "decalsBakedIntoModel": decals_baked,
                    "notes": self._customization_notes(decals_baked),
                },
                "files": [
                    "final_shoe.glb",
                    "final_shoe.obj",
                    "final_texture.png",
                    "preview_front.png",
                    "preview_side.png",
                    "preview_top.png",
                    "preview_back.png",
                ],
            },
        )

    def _summary(self, design_config: dict) -> str:
        sticker_count = len(design_config.get("stickers", []))
        text_count = len(design_config.get("texts", []))
        return (
            f"Shoe design with base color {design_config.get('baseColor', '#ffffff')}, "
            f"{sticker_count} sticker decal(s), and {text_count} text decal(s)."
        )

    def _customization_notes(self, decals_baked: bool) -> str:
        if decals_baked:
            return (
                "Sticker decals were exported as shrinkwrapped mesh overlays. "
                "Use design_config.json for editable layer metadata."
            )
        return "Use preview images and design_config.json as manual customization reference."

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _zip_export(self, export_dir: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in export_dir.rglob("*"):
                if path == zip_path or path.is_dir():
                    continue
                if "_work" in path.relative_to(export_dir).parts:
                    continue
                archive.write(path, path.relative_to(export_dir))
