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
    source_type: str = Field(default="scan", alias="sourceType")
    import_name: str | None = Field(default=None, alias="importName")
    error_message: str | None = Field(default=None, alias="errorMessage")
    model_asset_id: str | None = Field(default=None, alias="modelAssetId")
    updated_at: datetime = Field(alias="updatedAt")
    uploaded_passes: list[str] = Field(default_factory=list, alias="uploadedPasses")
    required_passes: list[str] = Field(default_factory=list, alias="requiredPasses")
    ready_for_processing: bool = Field(default=False, alias="readyForProcessing")
    processing_started: bool = Field(default=False, alias="processingStarted")
    web_design_url: str | None = Field(default=None, alias="webDesignUrl")


class ScanSessionResponse(CamelModel):
    id: str
    user_id: str = Field(alias="userId")
    status: str
    source_type: str = Field(default="scan", alias="sourceType")
    import_name: str | None = Field(default=None, alias="importName")
    error_message: str | None = Field(default=None, alias="errorMessage")
    model_asset_id: str | None = Field(default=None, alias="modelAssetId")
    web_design_url: str | None = Field(default=None, alias="webDesignUrl")
    uploaded_passes: list[str] = Field(default_factory=list, alias="uploadedPasses")
    required_passes: list[str] = Field(default_factory=list, alias="requiredPasses")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ScanUploadResponse(CamelModel):
    scan_session: ScanSessionResponse = Field(alias="scanSession")
    pass_type: str = Field(alias="passType")
    uploaded_passes: list[str] = Field(alias="uploadedPasses")
    required_passes: list[str] = Field(alias="requiredPasses")
    ready_for_processing: bool = Field(alias="readyForProcessing")
    processing_started: bool = Field(alias="processingStarted")
    web_design_url: str = Field(alias="webDesignUrl")
