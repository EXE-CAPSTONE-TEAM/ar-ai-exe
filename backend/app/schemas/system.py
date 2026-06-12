from pydantic import Field

from app.schemas.common import CamelModel


class ReconstructionToolStatus(CamelModel):
    name: str
    required: bool
    available: bool
    path: str | None = None
    configured_value: str = Field(alias="configuredValue")
    hint: str


class ReconstructionResourceStatus(CamelModel):
    name: str
    ok: bool
    available: float | None = None
    required: float
    unit: str
    message: str


class ReconstructionReadinessResponse(CamelModel):
    ready: bool
    message: str
    tools: list[ReconstructionToolStatus]
    resources: list[ReconstructionResourceStatus]
    settings: dict[str, float | int | bool | str]
    missing_tools: list[str] = Field(alias="missingTools")
    blocking_reasons: list[str] = Field(alias="blockingReasons")


class EditorCapabilityStatus(CamelModel):
    status: str
    available: bool
    path: str | None = None
    message: str


class EditorReadinessResponse(CamelModel):
    ready: bool
    message: str
    preview_renderer: EditorCapabilityStatus = Field(alias="previewRenderer")
    settings: dict[str, bool | str]
