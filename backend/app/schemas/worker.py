from __future__ import annotations

import json
import uuid
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


ExportFormat = Literal["glb", "obj"]
ImageMimeType = Literal["image/png", "image/jpeg", "image/webp"]


class WorkerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceDownloadCapability(WorkerModel):
    asset_id: uuid.UUID
    download_url: str = Field(min_length=8, max_length=8192)
    file_size_bytes: int = Field(gt=0, strict=True)
    mime_type: Literal["model/gltf-binary"]


class AssetDownloadCapability(WorkerModel):
    asset_id: uuid.UUID
    download_url: str = Field(min_length=8, max_length=8192)
    file_size_bytes: int = Field(gt=0, strict=True)
    mime_type: ImageMimeType


class OutputUploadCapability(WorkerModel):
    format: ExportFormat
    file_path: str = Field(min_length=1, max_length=512)
    upload_url: str = Field(min_length=8, max_length=8192)
    content_type: str = Field(min_length=1, max_length=100)


class BakeWorkerRequest(WorkerModel):
    job_id: uuid.UUID
    project_id: uuid.UUID
    design_config: dict[str, Any]
    formats: list[ExportFormat] = Field(min_length=1, max_length=2)
    source_model: SourceDownloadCapability
    asset_downloads: list[AssetDownloadCapability] = Field(
        default_factory=list,
        max_length=50,
    )
    outputs: list[OutputUploadCapability] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(set(self.formats)) != len(self.formats):
            raise ValueError("formats must not contain duplicates")

        output_formats = [item.format for item in self.outputs]
        if len(set(output_formats)) != len(output_formats):
            raise ValueError("outputs must not contain duplicate formats")
        if set(output_formats) != set(self.formats):
            raise ValueError("outputs must exactly match requested formats")

        expected_outputs = {
            "glb": (
                f"exports/{self.project_id}/{self.job_id}/final_shoe.glb",
                "model/gltf-binary",
            ),
            "obj": (
                f"exports/{self.project_id}/{self.job_id}/final_shoe.obj.zip",
                "application/zip",
            ),
        }
        for output in self.outputs:
            expected_path, expected_content_type = expected_outputs[output.format]
            if output.file_path != expected_path or output.content_type != expected_content_type:
                raise ValueError("output capability does not match the canonical job path")

        encoded_config = json.dumps(
            self.design_config,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded_config) > 2 * 1024 * 1024:
            raise ValueError("design_config exceeds the 2 MiB limit")

        configured_model_id = self.design_config.get(
            "modelAssetId",
            self.design_config.get("model_asset_id"),
        )
        if configured_model_id not in (None, ""):
            try:
                parsed_model_id = uuid.UUID(str(configured_model_id))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("design_config model asset ID is invalid") from exc
            if parsed_model_id != self.source_model.asset_id:
                raise ValueError("source capability does not match design_config")

        referenced_ids = _referenced_asset_ids(self.design_config)
        capability_ids = [item.asset_id for item in self.asset_downloads]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("asset capabilities must not contain duplicates")
        if set(capability_ids) != referenced_ids:
            raise ValueError("asset capabilities must exactly match design references")
        return self


class BakeWorkerExport(WorkerModel):
    format: ExportFormat
    file_path: str
    file_size_bytes: int = Field(gt=0, strict=True)


class BakeWorkerResponse(WorkerModel):
    exports: list[BakeWorkerExport]


def _referenced_asset_ids(design_config: dict[str, Any]) -> set[uuid.UUID]:
    stickers = design_config.get("stickers", [])
    texts = design_config.get("texts", [])
    if not isinstance(stickers, list) or not isinstance(texts, list):
        raise ValueError("design stickers and texts must be arrays")
    if len(stickers) + len(texts) > 50:
        raise ValueError("design cannot contain more than 50 decal layers")

    result: set[uuid.UUID] = set()
    for layers, camel_key, snake_key in (
        (stickers, "assetId", "asset_id"),
        (texts, "renderAssetId", "render_asset_id"),
    ):
        for layer in layers:
            if not isinstance(layer, dict):
                raise ValueError("design decal layers must be objects")
            raw_id = layer.get(camel_key) or layer.get(snake_key)
            if raw_id in (None, ""):
                continue
            try:
                result.add(uuid.UUID(str(raw_id)))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("design decal asset ID is invalid") from exc
    return result
