import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.common import CamelModel


OpaqueToken = Annotated[
    str,
    StringConstraints(
        min_length=32,
        max_length=256,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]


class ComputeGrantExchangeRequest(CamelModel):
    compute_grant: OpaqueToken = Field(alias="computeGrant")


class ComputeGrantExchangeResponse(CamelModel):
    access_token: str = Field(alias="accessToken")
    token_type: Literal["bearer"] = Field(default="bearer", alias="tokenType")
    expires_in: int = Field(gt=0, alias="expiresIn")
    project_id: uuid.UUID = Field(alias="projectId")
    project_name: str = Field(alias="projectName")
    web_project_url: str = Field(alias="webProjectUrl")


class ControlPlaneGrantClaimResponse(BaseModel):
    user_id: uuid.UUID
    project_id: uuid.UUID
    project_name: str = Field(min_length=1, max_length=100)
    completion_token: OpaqueToken
    web_project_url: str = Field(min_length=1, max_length=2048)


class ControlPlaneOutputUploadResponse(BaseModel):
    project_id: uuid.UUID
    asset_id: uuid.UUID
    file_path: str = Field(min_length=1, max_length=2048)
    upload_url: str | None = Field(default=None, max_length=8192)
    expires_in: int = Field(ge=0)
    already_completed: bool = False


class ControlPlaneOutputConfirmResponse(BaseModel):
    project_id: uuid.UUID
    model_asset_id: uuid.UUID
    status: str
    web_project_url: str = Field(min_length=1, max_length=2048)
