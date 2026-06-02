from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class DesignAssetResponse(CamelModel):
    id: str
    source_type: str = Field(alias="sourceType")
    file_name: str = Field(alias="fileName")
    content_type: str = Field(alias="contentType")
    size_bytes: int = Field(alias="sizeBytes")
    checksum: str
    download_url: str = Field(alias="downloadUrl")
    created_at: datetime = Field(alias="createdAt")
