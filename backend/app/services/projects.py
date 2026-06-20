from __future__ import annotations

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    AssetStatus,
    Design,
    ExportPackage,
    ModelAsset,
    Project,
    ProjectSourceType,
    ProjectStatus,
    ScanSession,
    User,
)
from app.schemas.design import DesignConfig, DesignResponse
from app.schemas.project import (
    EditorContextResponse,
    EditorModelAsset,
    EditorPermissions,
    ProjectCreate,
    ProjectDesignCreate,
    ProjectExportsResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectResponse,
)
from app.services.designs import DesignService
from app.services.export_packages import ExportPackageService
from app.services.model_assets import ModelAssetService


class ProjectService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User, payload: ProjectCreate) -> Project:
        project = Project(
            user_id=user.id,
            name=payload.name,
            status=ProjectStatus.DRAFT,
            source_type=payload.source_type,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def create_for_user(
        self,
        user: User,
        name: str,
        source_type: str = ProjectSourceType.SCAN,
    ) -> Project:
        project = Project(
            user_id=user.id,
            name=name,
            status=ProjectStatus.DRAFT,
            source_type=source_type,
        )
        self.db.add(project)
        self.db.flush()
        return project

    def list_for_user(self, user: User) -> ProjectListResponse:
        projects = self.db.scalars(
            select(Project)
            .where(Project.user_id == user.id)
            .order_by(desc(Project.updated_at))
        ).all()
        return ProjectListResponse(
            items=[
                ProjectListItem(
                    id=project.id,
                    name=project.name,
                    status=project.status,
                    thumbnailUrl=project.thumbnail_url,
                    updatedAt=project.updated_at,
                )
                for project in projects
            ]
        )

    def get_for_user(self, project_id: str, user: User) -> Project:
        project = self.db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise ApiError(404, "PROJECT_NOT_FOUND", "Project not found.")
        return project

    def response(self, project: Project) -> ProjectResponse:
        return ProjectResponse(
            id=project.id,
            name=project.name,
            status=project.status,
            thumbnailUrl=project.thumbnail_url,
            sourceType=project.source_type,
            createdAt=project.created_at,
            updatedAt=project.updated_at,
        )

    def editor_context(self, project_id: str, user: User) -> EditorContextResponse:
        project = self.get_for_user(project_id, user)
        model_asset = self.latest_model_asset(project)
        latest_design = self.latest_design(project, model_asset)
        return EditorContextResponse(
            project=self.response(project),
            modelAsset=self.editor_model_asset(project, model_asset) if model_asset else None,
            latestDesign=DesignService(self.db).response(latest_design) if latest_design else None,
            permissions=EditorPermissions(canEdit=True, canBake=True, canExport=True),
        )

    def latest_model_asset(self, project: Project) -> ModelAsset | None:
        return self.db.scalar(
            select(ModelAsset)
            .join(ScanSession, ModelAsset.scan_session_id == ScanSession.id)
            .where(ScanSession.project_id == project.id)
            .order_by(desc(ModelAsset.created_at))
        )

    def latest_design(self, project: Project, model_asset: ModelAsset | None = None) -> Design | None:
        clauses = [Design.project_id == project.id]
        if model_asset is not None:
            clauses.append(Design.model_asset_id == model_asset.id)
        return self.db.scalar(
            select(Design)
            .where(or_(*clauses))
            .order_by(desc(Design.updated_at), desc(Design.created_at))
        )

    def editor_model_asset(self, project: Project, asset: ModelAsset) -> EditorModelAsset:
        base = ModelAssetService(self.db).response(asset)
        texture_urls = [base.texture_url] if base.texture_url else []
        return EditorModelAsset(
            id=asset.id,
            projectId=project.id,
            status=asset.status,
            sourceType=asset.source_type,
            canonicalGlbUrl=base.glb_url,
            objUrl=base.obj_url,
            mtlUrl=base.mtl_url,
            textureUrls=texture_urls,
            scanSessionId=asset.scan_session_id,
            glbUrl=base.glb_url,
            textureUrl=base.texture_url,
            metadataUrl=base.metadata_url,
            qualityReportUrl=base.quality_report_url,
            objPackageZipUrl=base.obj_package_zip_url,
            qualityReport=base.quality_report,
            createdAt=asset.created_at,
        )

    def create_design(self, project_id: str, user: User, payload: ProjectDesignCreate) -> DesignResponse:
        project = self.get_for_user(project_id, user)
        asset = self.latest_model_asset(project)
        if not asset:
            raise ApiError(400, "MODEL_NOT_READY", "Project model is not ready.")
        if asset.status != AssetStatus.READY:
            raise ApiError(400, "MODEL_NOT_READY", "Project model is not ready.")

        config_payload = dict(payload.design_config)
        config_payload["modelAssetId"] = asset.id
        metadata = config_payload.get("metadata")
        config_payload["metadata"] = metadata if isinstance(metadata, dict) else {}
        config_payload["metadata"].setdefault("editorVersion", "1.0.0")
        config = DesignConfig.model_validate(config_payload)
        design = DesignService(self.db).create(
            user=user,
            model_asset_id=asset.id,
            name=payload.name or project.name,
            config=config,
            project_id=project.id,
        )
        project.status = ProjectStatus.READY
        self.db.commit()
        self.db.refresh(design)
        return DesignService(self.db).response(design)

    def exports(self, project_id: str, user: User) -> ProjectExportsResponse:
        project = self.get_for_user(project_id, user)
        exports = self.db.scalars(
            select(ExportPackage)
            .join(Design, ExportPackage.design_id == Design.id)
            .where(Design.project_id == project.id)
            .order_by(desc(ExportPackage.created_at))
        ).all()
        service = ExportPackageService(self.db)
        return ProjectExportsResponse(items=[service.response(export_package) for export_package in exports])
