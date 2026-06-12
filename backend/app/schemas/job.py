from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel


JobStatusValue = Literal["queued", "processing", "completed", "failed"]
JobTypeValue = Literal["bake"]


class JobResponse(CamelModel):
    id: str
    type: JobTypeValue
    status: JobStatusValue
    progress: int = 0
    error_message: str | None = Field(default=None, alias="errorMessage")
    design_id: str | None = Field(default=None, alias="designId")
    project_id: str | None = Field(default=None, alias="projectId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
