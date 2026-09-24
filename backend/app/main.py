from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    control_plane_mobile,
    design_assets,
    designs,
    exports,
    jobs,
    models,
    projects,
    scan_sessions,
    system,
    worker,
)
from app.core.config import Settings, get_settings
from app.core.errors import http_exception_handler, validation_exception_handler
from app.core.storage import ensure_storage_directories
from app.db.database import Base, engine
from app import models as _models  # noqa: F401


settings = get_settings()


def create_app(custom_settings: Settings | None = None) -> FastAPI:
    current_settings = custom_settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ensure_storage_directories(current_settings)
        if current_settings.database_auto_create_tables:
            Base.metadata.create_all(bind=engine)
        yield

    application = FastAPI(
        title=current_settings.app_name,
        debug=current_settings.debug,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1|172\.16\.1\.232):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if current_settings.app_role.lower() == "relay":
        application.include_router(scan_sessions.router, prefix=current_settings.api_prefix)
        application.include_router(control_plane_mobile.router, prefix=current_settings.api_prefix)
    else:
        application.include_router(auth.router, prefix=current_settings.api_prefix)
        application.include_router(projects.router, prefix=current_settings.api_prefix)
        application.include_router(scan_sessions.router, prefix=current_settings.api_prefix)
        application.include_router(models.router, prefix=current_settings.api_prefix)
        application.include_router(design_assets.router, prefix=current_settings.api_prefix)
        application.include_router(designs.router, prefix=current_settings.api_prefix)
        application.include_router(exports.router, prefix=current_settings.api_prefix)
        application.include_router(jobs.router, prefix=current_settings.api_prefix)
        application.include_router(system.router, prefix=current_settings.api_prefix)
        application.include_router(control_plane_mobile.router, prefix=current_settings.api_prefix)
        application.include_router(worker.router)

    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)

    @application.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": current_settings.app_name,
            "environment": current_settings.environment,
        }

    return application


app = create_app()
