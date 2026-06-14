from __future__ import annotations

import shutil

from app.core.config import get_settings


class EditorReadinessService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def check(self) -> dict:
        show_local_paths = self.settings.environment in {"desktop", "local", "dev", "development", "test"}
        blender_path = shutil.which(self.settings.blender_bin)
        preview_available = blender_path is not None
        preview_status = "installed" if preview_available else "missing"
        preview_message = (
            "Preview renderer is ready."
            if preview_available
            else "Preview renderer is not installed. Install Blender to bake previews and exports."
        )
        return {
            "ready": preview_available,
            "message": (
                "Editor capabilities are ready."
                if preview_available
                else "Editor can open models, but preview baking needs Blender."
            ),
            "previewRenderer": {
                "status": preview_status,
                "available": preview_available,
                "path": blender_path if show_local_paths else None,
                "message": preview_message,
            },
            "settings": {
                "environment": self.settings.environment,
                "enableRealReconstruction": self.settings.enable_real_reconstruction,
                "enableInlineBakeFallback": self.settings.enable_inline_bake_fallback,
                "blenderBin": self.settings.blender_bin if show_local_paths else "configured",
            },
        }
