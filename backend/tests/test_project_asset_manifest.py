from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import ApiError
from app.db.database import Base
from app.models import AssetVersionType, Project, ProjectStatus, User
from app.services.asset_versions import AssetVersionFileInput, AssetVersionService
from app.services.project_asset_manifest import ProjectAssetManifestService


class ManifestStorage:
    def __init__(self, signed: bool = False, signed_raises: bool = False) -> None:
        self.signed = signed
        self.signed_raises = signed_raises
        self.objects = {"models/shoe.glb": b"glb"}

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None:
        if self.signed_raises:
            raise RuntimeError("storage unavailable")
        return f"https://storage.example/{key}?signed=1" if self.signed else None

    def local_path(self, key: str) -> Path | None:
        return None


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_project(db):
    owner = User(id="owner", name="Owner", email="owner@example.com")
    other = User(id="other", name="Other", email="other@example.com")
    project = Project(
        id="proj_001",
        user_id=owner.id,
        name="Shoe",
        status=ProjectStatus.READY,
        source_type="scan",
    )
    db.add_all([owner, other, project])
    db.commit()
    return owner, other, project


def manifest_service(db, monkeypatch, *, signed: bool = False, signed_raises: bool = False):
    storage = ManifestStorage(signed=signed, signed_raises=signed_raises)
    monkeypatch.setattr(
        "app.services.project_asset_manifest.get_storage_service",
        lambda: storage,
    )
    return ProjectAssetManifestService(db)


def publish_model(db, project):
    return AssetVersionService(db).publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        logical_key="primary",
        source_type="scan",
        files=[
            AssetVersionFileInput(
                file_type="glb",
                canonical_name="shoe_preview.glb",
                storage_key="models/shoe.glb",
                content_type="model/gltf-binary",
                size_bytes=3,
                checksum="checksum",
            )
        ],
    )


def test_manifest_always_returns_stable_sections(monkeypatch) -> None:
    db = make_session()
    owner, _, project = seed_project(db)
    service = manifest_service(db, monkeypatch)

    manifest = service.manifest_for_user(project.id, owner)

    assert manifest.project.id == project.id
    assert manifest.model.latest_version is None
    assert manifest.design.latest_revision is None
    assert manifest.preview.latest_version is None
    assert manifest.exports.latest_version is None
    assert manifest.exports.items == []


def test_manifest_returns_latest_model_with_local_fallback_url(monkeypatch) -> None:
    db = make_session()
    owner, _, project = seed_project(db)
    version = publish_model(db, project)
    db.commit()
    manifest = manifest_service(db, monkeypatch).manifest_for_user(project.id, owner)

    assert manifest.model.latest_version is not None
    assert manifest.model.latest_version.asset_version_id == version.id
    assert manifest.model.latest_version.files[0].url == (
        f"/api/projects/{project.id}/asset-versions/{version.id}/files/glb"
    )
    assert manifest.design.latest_revision is None


def test_manifest_uses_signed_storage_url(monkeypatch) -> None:
    db = make_session()
    owner, _, project = seed_project(db)
    publish_model(db, project)
    db.commit()

    manifest = manifest_service(db, monkeypatch, signed=True).manifest_for_user(
        project.id,
        owner,
    )

    assert manifest.model.latest_version is not None
    assert manifest.model.latest_version.files[0].url.startswith("https://storage.example/")


def test_manifest_falls_back_when_signed_url_generation_fails(monkeypatch) -> None:
    db = make_session()
    owner, _, project = seed_project(db)
    version = publish_model(db, project)
    db.commit()

    manifest = manifest_service(db, monkeypatch, signed_raises=True).manifest_for_user(
        project.id,
        owner,
    )

    assert manifest.model.latest_version is not None
    assert manifest.model.latest_version.files[0].url == (
        f"/api/projects/{project.id}/asset-versions/{version.id}/files/glb"
    )


def test_manifest_hides_foreign_project(monkeypatch) -> None:
    db = make_session()
    _, other, project = seed_project(db)

    with pytest.raises(ApiError) as exc:
        manifest_service(db, monkeypatch).manifest_for_user(project.id, other)

    assert exc.value.status_code == 404


def test_version_file_download_is_project_scoped(monkeypatch) -> None:
    db = make_session()
    owner, other, project = seed_project(db)
    version = publish_model(db, project)
    db.commit()
    service = manifest_service(db, monkeypatch)

    asset_file, payload = service.file_for_user(project.id, version.id, " GLB ", owner)

    assert asset_file.canonical_name == "shoe_preview.glb"
    assert payload == b"glb"
    with pytest.raises(ApiError):
        service.file_for_user(project.id, version.id, "glb", other)
