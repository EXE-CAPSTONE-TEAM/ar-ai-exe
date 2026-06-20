from __future__ import annotations

import argparse
import os
from pathlib import Path


APP_DIR_NAME = "KusShoes Editor"
DEMO_MODEL_RELATIVE_PATHS = [
    Path("data") / "3DModel.glb",
    Path("resources") / "data" / "3DModel.glb",
    Path("..") / "data" / "3DModel.glb",
]


def main() -> None:
    args = parse_args()
    app_data = desktop_app_data_dir()
    runtime_root = app_data / "runtime"
    storage_root = app_data / "storage"
    blender_bin = runtime_root / "tools" / "blender" / "blender-4.5.1-windows-x64" / "blender.exe"

    storage_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "logs").mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("ENVIRONMENT", "desktop")
    os.environ.setdefault("STORAGE_ROOT", str(storage_root))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{(storage_root / 'app.db').as_posix()}")
    os.environ.setdefault("DATABASE_AUTO_CREATE_TABLES", "true")
    os.environ.setdefault("ENABLE_INLINE_BAKE_FALLBACK", "true")
    os.environ.setdefault("ENABLE_REAL_RECONSTRUCTION", "false")
    os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
    os.environ.setdefault(
        "CORS_ORIGINS",
        f'["http://127.0.0.1:{args.frontend_port}", "http://localhost:{args.frontend_port}"]',
    )
    os.environ.setdefault("BLENDER_BIN", str(blender_bin))

    if not args.skip_seed:
        seed_demo_if_possible()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the KusShoes desktop backend sidecar.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--skip-seed", action="store_true")
    return parser.parse_args()


def desktop_app_data_dir() -> Path:
    configured = os.environ.get("KUSSHOES_DESKTOP_APP_DATA")
    if configured:
        return Path(configured)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.replace(' ', '').lower()}"


def seed_demo_if_possible() -> None:
    model_path = demo_model_path()
    if not model_path:
        return

    from app.db.database import Base, engine
    from app.scripts.seed_desktop_demo_project import seed_demo_project

    Base.metadata.create_all(bind=engine)
    seed_demo_project(model_path=model_path, name="KusShoes Desktop Demo")


def demo_model_path() -> Path | None:
    configured = os.environ.get("KUSSHOES_DESKTOP_DEMO_MODEL")
    if configured and Path(configured).is_file():
        return Path(configured).resolve()

    base_dirs = [
        Path.cwd(),
        Path(__file__).resolve().parents[2],
        Path(getattr(__import__("sys"), "executable", "")).resolve().parent,
    ]
    for base_dir in base_dirs:
        for relative_path in DEMO_MODEL_RELATIVE_PATHS:
            candidate = (base_dir / relative_path).resolve()
            if candidate.is_file():
                return candidate
    return None


if __name__ == "__main__":
    main()
