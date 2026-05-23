import json

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.schemas.scan import ScanMetadata


def parse_scan_metadata(raw_metadata: str) -> ScanMetadata:
    try:
        payload = json.loads(raw_metadata)
        return ScanMetadata.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid scan metadata: {exc}",
        ) from exc


def scan_metadata_bytes(metadata: ScanMetadata) -> bytes:
    return json.dumps(metadata.model_dump(by_alias=True), indent=2).encode("utf-8")
