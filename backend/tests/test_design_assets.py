import pytest
from fastapi import HTTPException, status

from app.models import DesignAsset, User
from app.services.design_assets import DesignAssetService, UploadedDesignAsset


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"png-data"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str):
        from app.services.storage import StoredObject, checksum_bytes

        self.objects[key] = (data, content_type)
        return StoredObject(
            key=key,
            size_bytes=len(data),
            content_type=content_type,
            checksum=checksum_bytes(data),
        )

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key][0]

    def exists(self, key: str) -> bool:
        return key in self.objects


class FakeDb:
    def __init__(self, asset: DesignAsset | None = None) -> None:
        self.asset = asset
        self.added: DesignAsset | None = None

    def add(self, asset: DesignAsset) -> None:
        self.added = asset
        self.asset = asset

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, asset: DesignAsset) -> None:
        pass

    def get(self, model, asset_id: str):
        if model is DesignAsset and self.asset and self.asset.id == asset_id:
            return self.asset
        return None


def design_asset_service(db: FakeDb | None = None) -> DesignAssetService:
    service = object.__new__(DesignAssetService)
    service.db = db or FakeDb()
    service.storage = FakeStorage()
    return service


def test_create_design_asset_validates_and_stores_png() -> None:
    service = design_asset_service()
    user = User(id="user_001", name="Demo", email="demo@example.com")

    asset = service.create(
        user,
        UploadedDesignAsset(file_name="My Artwork!.png", content_type="image/png", data=PNG_BYTES),
        "canvas",
    )

    assert asset.user_id == "user_001"
    assert asset.source_type == "canvas"
    assert asset.content_type == "image/png"
    assert asset.file_name == "My_Artwork.png"
    assert asset.storage_path.startswith("design-assets/user_001/asset_")
    assert asset.size_bytes == len(PNG_BYTES)
    assert service.storage.exists(asset.storage_path)


def test_design_asset_rejects_unsupported_mime() -> None:
    service = design_asset_service()

    with pytest.raises(HTTPException) as exc:
        service.create(
            User(id="user_001", name="Demo", email="demo@example.com"),
            UploadedDesignAsset(file_name="bad.gif", content_type="image/gif", data=b"GIF89a"),
            "upload",
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_design_asset_rejects_oversized_image() -> None:
    service = design_asset_service()

    with pytest.raises(HTTPException) as exc:
        service.create(
            User(id="user_001", name="Demo", email="demo@example.com"),
            UploadedDesignAsset(file_name="large.png", content_type="image/png", data=PNG_BYTES + b"x" * (5 * 1024 * 1024)),
            "upload",
        )

    assert exc.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE


def test_get_for_user_hides_other_users_assets() -> None:
    asset = DesignAsset(
        id="asset_001",
        user_id="owner",
        source_type="upload",
        file_name="art.png",
        storage_path="design-assets/owner/asset_001.png",
        content_type="image/png",
        size_bytes=len(PNG_BYTES),
        checksum="checksum",
    )
    service = design_asset_service(FakeDb(asset))

    with pytest.raises(HTTPException) as exc:
        service.get_for_user(asset.id, User(id="other", name="Other", email="other@example.com"))

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
