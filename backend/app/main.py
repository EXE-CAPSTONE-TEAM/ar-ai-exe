from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, design_assets, designs, exports, models, scan_sessions, system
from app.core.config import get_settings
from app.core.storage import ensure_storage_directories
from app.db.database import Base, engine
from app import models as _models  # noqa: F401


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_storage_directories(settings)
    if settings.database_auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(scan_sessions.router, prefix=settings.api_prefix)
app.include_router(models.router, prefix=settings.api_prefix)
app.include_router(design_assets.router, prefix=settings.api_prefix)
app.include_router(designs.router, prefix=settings.api_prefix)
app.include_router(exports.router, prefix=settings.api_prefix)
app.include_router(system.router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }
