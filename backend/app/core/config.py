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
    database_url: str = "sqlite:///./storage/app.db"

    enable_real_reconstruction: bool = False
    colmap_bin: str = "colmap"
    openmvs_bin_dir: str = ""
    blender_bin: str = "blender"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
