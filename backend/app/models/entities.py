from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ScanStatus:
    CREATED = "created"
    WAITING_FOR_UPLOADS = "waiting_for_uploads"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    TOOLCHAIN_UNAVAILABLE = "toolchain_unavailable"
    EXTRACTING_FRAMES = "extracting_frames"
    FILTERING_FRAMES = "filtering_frames"
    PREPARING_RECONSTRUCTION = "preparing_reconstruction"
    RECONSTRUCTING = "reconstructing"
    CLEANING_MESH = "cleaning_mesh"
    UV_UNWRAPPING = "uv_unwrapping"
    TEXTURE_BAKING = "texture_baking"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanSource:
    SCAN = "scan"
    IMPORT = "import"


class DesignStatus:
    DRAFT = "draft"
    EXPORTED = "exported"


class DesignPreviewStatus:
    NONE = "none"
    READY = "ready"
    FAILED = "failed"


class ExportStatus:
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("user"))
    role: Mapped[str] = mapped_column(String(32), default="demo_user")
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    scan_sessions: Mapped[list["ScanSession"]] = relationship(back_populates="user")
    designs: Mapped[list["Design"]] = relationship(back_populates="user")
    design_assets: Mapped[list["DesignAsset"]] = relationship(back_populates="user")


class ScanSession(Base):
    __tablename__ = "scan_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("scan"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=ScanStatus.CREATED, index=True)
    source_type: Mapped[str] = mapped_column(String(32), default=ScanSource.SCAN, index=True)
    import_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    raw_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    web_design_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_video_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_video_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_video_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    side_video_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    side_video_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    side_video_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    top_video_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_video_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    top_video_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="scan_sessions")
    model_asset: Mapped["ModelAsset | None"] = relationship(
        back_populates="scan_session",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ModelAsset(Base):
    __tablename__ = "model_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("model"))
    scan_session_id: Mapped[str] = mapped_column(
        ForeignKey("scan_sessions.id"),
        unique=True,
        index=True,
    )
    glb_path: Mapped[str] = mapped_column(Text)
    obj_path: Mapped[str] = mapped_column(Text)
    mtl_path: Mapped[str] = mapped_column(Text)
    texture_path: Mapped[str] = mapped_column(Text)
    metadata_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_report_path: Mapped[str] = mapped_column(Text)
    obj_package_zip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    glb_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    glb_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    glb_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    obj_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    obj_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    obj_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mtl_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mtl_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mtl_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    texture_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    texture_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    texture_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quality_report_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_report_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quality_report_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    obj_package_zip_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    obj_package_zip_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    obj_package_zip_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    scan_session: Mapped[ScanSession] = relationship(back_populates="model_asset")
    designs: Mapped[list["Design"]] = relationship(back_populates="model_asset")


class Design(Base):
    __tablename__ = "designs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("design"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    model_asset_id: Mapped[str] = mapped_column(ForeignKey("model_assets.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    design_config_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=DesignStatus.DRAFT, index=True)
    preview_glb_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_glb_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preview_glb_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preview_glb_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    preview_status: Mapped[str] = mapped_column(String(32), default=DesignPreviewStatus.NONE, index=True)
    preview_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="designs")
    model_asset: Mapped[ModelAsset] = relationship(back_populates="designs")
    export_packages: Mapped[list["ExportPackage"]] = relationship(back_populates="design")


class DesignAsset(Base):
    __tablename__ = "design_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("asset"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    file_name: Mapped[str] = mapped_column(String(180))
    storage_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="design_assets")


class ExportPackage(Base):
    __tablename__ = "export_packages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("export"))
    design_id: Mapped[str] = mapped_column(ForeignKey("designs.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=ExportStatus.COMPLETED)
    glb_path: Mapped[str] = mapped_column(Text)
    obj_path: Mapped[str] = mapped_column(Text)
    mtl_path: Mapped[str] = mapped_column(Text)
    texture_path: Mapped[str] = mapped_column(Text)
    preview_images_path: Mapped[str] = mapped_column(Text)
    production_notes_path: Mapped[str] = mapped_column(Text)
    zip_path: Mapped[str] = mapped_column(Text)
    zip_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zip_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    zip_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    design: Mapped[Design] = relationship(back_populates="export_packages")
