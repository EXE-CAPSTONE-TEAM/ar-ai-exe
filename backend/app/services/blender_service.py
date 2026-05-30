import shutil
from pathlib import Path

from app.core.config import get_settings


class BlenderService:
    def __init__(self):
        self.settings = get_settings()

    def is_available(self) -> bool:
        return shutil.which(self.settings.blender_bin) is not None

    def require_available(self) -> str:
        binary = shutil.which(self.settings.blender_bin)
        if not binary:
            raise RuntimeError(
                f"Blender binary '{self.settings.blender_bin}' was not found. "
                "Install Blender or set BLENDER_BIN."
            )
        return binary

    def cleanup_export_command(
        self, script_path: Path, input_mesh_path: Path, output_dir: Path
    ) -> list[str]:
        return [
            self.require_available(),
            "--background",
            "--python",
            str(script_path),
            "--",
            str(input_mesh_path),
            str(output_dir),
        ]

    def sculpt_bake_command(
        self,
        script_path: Path,
        input_mesh_path: Path,
        output_dir: Path,
        *,
        voxel_size: float,
        smooth_iterations: int,
        smooth_factor: float,
        decimate_ratio: float,
        normal_map_size: int,
        texture_size: int,
    ) -> list[str]:
        """Build the Blender CLI command for auto-sculpt & bake with tunable parameters."""
        return [
            self.require_available(),
            "--background",
            "--python",
            str(script_path),
            "--",
            str(input_mesh_path),
            str(output_dir),
            "--voxel-size",
            str(voxel_size),
            "--smooth-iterations",
            str(smooth_iterations),
            "--smooth-factor",
            str(smooth_factor),
            "--decimate-ratio",
            str(decimate_ratio),
            "--normal-map-size",
            str(normal_map_size),
            "--texture-size",
            str(texture_size),
        ]
