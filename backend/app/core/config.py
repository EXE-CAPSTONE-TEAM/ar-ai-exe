from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-backed application settings."""

    app_name: str = "Shoe Visual Customizer API"
    environment: str = "local"
    debug: bool = True
    api_prefix: str = "/api"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    storage_root: Path = Path("storage")
    storage_backend: str = "local"
    storage_public_base_url: str = ""
    s3_endpoint_url: str = ""
    s3_region_name: str = "auto"
    s3_bucket_name: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    database_url: str = "sqlite:///./storage/app.db"
    database_auto_create_tables: bool = True
    web_app_base_url: str = "http://localhost:5173"
    marketing_login_url: str = "https://kusshoes.vn/login"
    jwt_secret_key: str = "local-dev-jwt-secret-change-me-32bytes-min"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 1440
    auth_cookie_name: str = "kusshoes_access_token"
    auth_cookie_domain: str = ""
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    csrf_cookie_name: str = "kusshoes_csrf_token"
    csrf_header_name: str = "x-csrf-token"
    enable_demo_auth: bool = True
    demo_access_token: str = "local-demo-token-change-me"
    demo_user_email: str = "demo@shoe-customizer.local"
    max_upload_size_mb: int = 250
    redis_url: str = "redis://localhost:6379/0"
    rq_queue_name: str = "kusshoes-jobs"
    rq_job_timeout_seconds: int = 7200
    enable_inline_bake_fallback: bool = False

    enable_real_reconstruction: bool = True
    colmap_bin: str = "colmap"
    openmvs_bin_dir: str = ""
    blender_bin: str = "blender"
    ffmpeg_bin: str = "ffmpeg"
    reconstruction_frame_fps: float = 2.0
    reconstruction_max_frames_per_pass: int = 90
    reconstruction_min_brightness: float = 28.0
    reconstruction_min_sharpness: float = 95.0
    reconstruction_duplicate_hamming_threshold: int = 4
    reconstruction_command_timeout_seconds: int = 7200
    reconstruction_max_threads: int = 4
    reconstruction_min_available_memory_gb: float = 4.0
    reconstruction_min_free_storage_gb: float = 8.0
    mesh_cleanup_target_max_dimension: float = 2.4
    mesh_cleanup_decimate_triangle_threshold: int = 250_000
    mesh_cleanup_decimate_ratio: float = 0.75

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def resolved_storage_root(self) -> Path:
        if self.storage_root.is_absolute():
            return self.storage_root
        return BACKEND_ROOT / self.storage_root

    @property
    def resolved_database_url(self) -> str:
        if not self.database_url.startswith("sqlite:///./"):
            return self.database_url
        relative_path = self.database_url.replace("sqlite:///./", "", 1)
        return f"sqlite:///{(BACKEND_ROOT / relative_path).as_posix()}"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Normalize common Postgres URLs to the installed psycopg SQLAlchemy driver."""
        url = self.resolved_database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
