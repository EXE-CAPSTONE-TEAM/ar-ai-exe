from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel


class ShoeMetadata(CamelModel):
    size_system: Literal["EU", "US", "UK", "CM"] = Field(alias="sizeSystem")
    size: str = Field(min_length=1)
    side: Literal["left", "right", "both"]
    type: Literal["sneaker", "running", "boot", "sandal", "other"]
    material: Literal["canvas", "leather", "synthetic", "mesh", "unknown"]
    condition: str = Field(min_length=1)


class MeasurementMetadata(CamelModel):
    length_cm: float = Field(gt=0, alias="lengthCm")
    width_cm: float = Field(gt=0, alias="widthCm")


class ScanSetupMetadata(CamelModel):
    calibration_reference: str = Field(min_length=1, alias="calibrationReference")
    lighting: str = Field(min_length=1)
    background: str = Field(min_length=1)


class ScanMetadata(CamelModel):
    shoe: ShoeMetadata
    measurements: MeasurementMetadata
    scan_setup: ScanSetupMetadata = Field(alias="scanSetup")
    customization_goal: list[str] = Field(min_length=1, alias="customizationGoal")


class ScanSessionCreate(CamelModel):
    metadata: ScanMetadata | None = None


class ScanStatusResponse(CamelModel):
    id: str
    status: str
    error_message: str | None = Field(default=None, alias="errorMessage")
    model_asset_id: str | None = Field(default=None, alias="modelAssetId")
    updated_at: datetime = Field(alias="updatedAt")


class ScanSessionResponse(CamelModel):
    id: str
    user_id: str = Field(alias="userId")
    status: str
    error_message: str | None = Field(default=None, alias="errorMessage")
    model_asset_id: str | None = Field(default=None, alias="modelAssetId")
    web_design_url: str | None = Field(default=None, alias="webDesignUrl")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ScanUploadResponse(CamelModel):
    scan_session: ScanSessionResponse = Field(alias="scanSession")
    processing_started: bool = Field(alias="processingStarted")
    web_design_url: str = Field(alias="webDesignUrl")
