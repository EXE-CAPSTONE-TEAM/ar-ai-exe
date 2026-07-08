from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.errors import ApiError
from app.db.database import Base
from app.models import (
    AssetVersion,
    AssetVersionFile,
    AssetVersionLegacyLink,
    AssetVersionStatus,
    AssetVersionType,
    Project,
    ProjectStatus,
    ScanSession,
    User,
)
from app.services.asset_versions import (
    DEFAULT_LOGICAL_KEY,
    AssetVersionFileInput,
    AssetVersionService,
)
from app.services.model_assets import ModelAssetFiles, ModelAssetService
from app.services.storage import StoredObject, checksum_bytes


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self.objects[key] = data
        return StoredObject(
            key=key,
            size_bytes=len(data),
            content_type=content_type,
            checksum=checksum_bytes(data),
        )

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None:
        return None

    def local_path(self, key: str) -> Path | None:
        return None


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_fk_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def project_fixture(db):
    user = User(id="user_001", name="Owner", email="owner@example.com")
    project = Project(
        id="proj_001",
        user_id=user.id,
        name="Shoe",
        status=ProjectStatus.DRAFT,
        source_type="scan",
    )
    db.add_all([user, project])
    db.commit()
    return user, project


def file_input(name: str = "asset.bin") -> AssetVersionFileInput:
    return AssetVersionFileInput(
        file_type="binary",
        canonical_name=name,
        storage_key=f"objects/{name}",
        content_type="application/octet-stream",
        size_bytes=4,
        checksum="checksum",
    )


def test_latest_version_uses_highest_published_version_number() -> None:
    db = make_session()
    _, project = project_fixture(db)
    service = AssetVersionService(db)

    first = service.publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        logical_key="primary",
        source_type="scan",
        files=[file_input("first.bin")],
    )
    second = service.publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        logical_key="primary",
        source_type="scan",
        files=[file_input("second.bin")],
    )
    db.commit()

    latest = service.latest_published(project.id, AssetVersionType.MODEL)

    assert first.version_number == 1
    assert second.version_number == 2
    assert latest is not None
    assert latest.id == second.id


def test_version_queries_normalize_asset_type_and_logical_key() -> None:
    db = make_session()
    _, project = project_fixture(db)
    service = AssetVersionService(db)
    service.publish(
        project=project,
        asset_type=" Model ",
        logical_key=f" {DEFAULT_LOGICAL_KEY.upper()} ",
        source_type="scan",
        files=[file_input("normalized.bin")],
    )
    db.commit()

    assert service.next_version_number(project.id, " MODEL ", f" {DEFAULT_LOGICAL_KEY.upper()} ") == 2
    assert service.latest_published(project.id, " MODEL ", f" {DEFAULT_LOGICAL_KEY.upper()} ") is not None
    assert len(service.list_published(project.id, " MODEL ", f" {DEFAULT_LOGICAL_KEY.upper()} ")) == 1


def test_latest_version_ignores_higher_failed_version() -> None:
    db = make_session()
    _, project = project_fixture(db)
    service = AssetVersionService(db)
    published = service.publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        logical_key="primary",
        source_type="scan",
        files=[file_input()],
    )
    failed = service.publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        logical_key="failed-slot",
        source_type="scan",
        files=[file_input("failed.bin")],
    )
    failed.logical_key = "primary"
    failed.version_number = 2
    failed.status = AssetVersionStatus.FAILED
    db.commit()

    latest = service.latest_published(project.id, AssetVersionType.MODEL)

    assert latest is not None
    assert latest.id == published.id


def test_non_model_asset_version_does_not_require_legacy_link() -> None:
    db = make_session()
    _, project = project_fixture(db)
    version = AssetVersionService(db).publish(
        project=project,
        asset_type=AssetVersionType.EXPORT,
        logical_key="primary",
        source_type="generated",
        files=[file_input("export.zip")],
    )
    db.commit()

    assert version.project_id == project.id
    assert version.asset_type == AssetVersionType.EXPORT
    assert version.legacy_links == []


def test_asset_version_parent_children_relationship() -> None:
    db = make_session()
    _, project = project_fixture(db)
    service = AssetVersionService(db)
    parent = service.publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        source_type="scan",
        files=[file_input("model.glb")],
    )
    child = service.publish(
        project=project,
        asset_type=AssetVersionType.PREVIEW,
        source_type="generated",
        parent_asset_version_id=parent.id,
        files=[file_input("preview.glb")],
    )
    db.commit()

    assert child.parent == parent
    assert parent.children == [child]


def test_parent_asset_version_delete_sets_child_parent_to_null() -> None:
    db = make_fk_session()
    _, project = project_fixture(db)
    service = AssetVersionService(db)
    parent = service.publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        source_type="scan",
        files=[file_input("model.glb")],
    )
    child = service.publish(
        project=project,
        asset_type=AssetVersionType.PREVIEW,
        source_type="generated",
        parent_asset_version_id=parent.id,
        files=[file_input("preview.glb")],
    )
    child_id = child.id
    db.commit()

    db.execute(delete(AssetVersion).where(AssetVersion.id == parent.id))
    db.commit()

    remaining_child = db.get(AssetVersion, child_id)
    assert remaining_child is not None
    assert remaining_child.parent_asset_version_id is None


def test_asset_version_delete_cascades_files_and_legacy_links() -> None:
    db = make_fk_session()
    _, project = project_fixture(db)
    version = AssetVersionService(db).publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        source_type="scan",
        files=[file_input("model.glb")],
        legacy_type="model_asset",
        legacy_id="model_001",
    )
    version_id = version.id
    db.commit()

    db.execute(delete(AssetVersion).where(AssetVersion.id == version_id))
    db.commit()

    assert db.scalar(select(func.count()).select_from(AssetVersionFile)) == 0
    assert db.scalar(select(func.count()).select_from(AssetVersionLegacyLink)) == 0


def test_project_delete_is_restricted_when_asset_versions_exist() -> None:
    db = make_fk_session()
    _, project = project_fixture(db)
    AssetVersionService(db).publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        source_type="scan",
        files=[file_input("model.glb")],
    )
    db.commit()

    with pytest.raises(IntegrityError):
        db.execute(delete(Project).where(Project.id == project.id))
        db.commit()


def test_legacy_link_uniqueness_is_unambiguous() -> None:
    db = make_session()
    _, project = project_fixture(db)
    service = AssetVersionService(db)
    service.publish(
        project=project,
        asset_type=AssetVersionType.MODEL,
        logical_key="primary",
        source_type="scan",
        files=[file_input("first.glb")],
        legacy_type="model_asset",
        legacy_id="model_001",
    )
    with pytest.raises(IntegrityError):
        service.publish(
            project=project,
            asset_type=AssetVersionType.MODEL,
            logical_key="alternate",
            source_type="scan",
            files=[file_input("second.glb")],
            legacy_type="model_asset",
            legacy_id="model_001",
        )


@pytest.mark.parametrize(
    ("storage_key", "content_type"),
    [
        ("", "application/octet-stream"),
        ("../asset.bin", "application/octet-stream"),
        ("objects/../asset.bin", "application/octet-stream"),
        ("/objects/asset.bin", "application/octet-stream"),
        ("objects\\asset.bin", "application/octet-stream"),
        ("objects/asset\r\n.bin", "application/octet-stream"),
        (f"objects/{'a' * 1025}", "application/octet-stream"),
        ("objects/asset.bin", ""),
        ("objects/asset.bin", "text/plain\r\nx-bad: 1"),
        ("objects/asset.bin", f"text/{'a' * 116}"),
    ],
)
def test_publish_validates_storage_key_and_content_type(
    storage_key: str,
    content_type: str,
) -> None:
    db = make_session()
    _, project = project_fixture(db)
    service = AssetVersionService(db)

    with pytest.raises(ApiError):
        service.publish(
            project=project,
            asset_type=AssetVersionType.MODEL,
            source_type="scan",
            files=[
                AssetVersionFileInput(
                    file_type="binary",
                    canonical_name="asset.bin",
                    storage_key=storage_key,
                    content_type=content_type,
                    size_bytes=4,
                    checksum="checksum",
                )
            ],
        )


def test_model_asset_creation_publishes_project_owned_version(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db = make_session()
    user, project = project_fixture(db)
    scan = ScanSession(
        id="scan_001",
        user_id=user.id,
        project_id=project.id,
        status="completed",
        source_type="scan",
    )
    db.add(scan)
    db.commit()
    storage = FakeStorage()
    monkeypatch.setattr("app.services.model_assets.get_storage_service", lambda: storage)
    paths = {}
    for name in (
        "shoe_preview.glb",
        "shoe.obj",
        "shoe.mtl",
        "shoe_texture.png",
        "metadata.json",
        "quality_report.json",
        "shoe_obj_package.zip",
    ):
        path = tmp_path / name
        path.write_bytes(name.encode("utf-8"))
        paths[name] = path

    asset = ModelAssetService(db).create_from_files(
        scan.id,
        ModelAssetFiles(
            glb=paths["shoe_preview.glb"],
            obj=paths["shoe.obj"],
            mtl=paths["shoe.mtl"],
            texture=paths["shoe_texture.png"],
            metadata=paths["metadata.json"],
            quality_report=paths["quality_report.json"],
            obj_package_zip=paths["shoe_obj_package.zip"],
        ),
    )
    version = AssetVersionService(db).latest_published(project.id, AssetVersionType.MODEL)

    assert version is not None
    assert version.project_id == project.id
    assert AssetVersionService.legacy_id(version, "model_asset") == asset.id
    assert len(version.files) == 7
    assert all(f"versions/{version.id}" in item.storage_key for item in version.files)
