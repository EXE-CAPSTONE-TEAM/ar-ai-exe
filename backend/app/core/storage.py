from pathlib import Path

from app.core.config import Settings


STORAGE_DIRECTORIES = {
    "raw_scans": "raw-scans",
    "frames": "frames",
    "models": "models",
    "designs": "designs",
    "exports": "exports",
}


def ensure_storage_directories(settings: Settings) -> dict[str, Path]:
    storage_root = settings.resolved_storage_root
    storage_root.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for key, folder_name in STORAGE_DIRECTORIES.items():
        path = storage_root / folder_name
        path.mkdir(parents=True, exist_ok=True)
        paths[key] = path

    return paths
