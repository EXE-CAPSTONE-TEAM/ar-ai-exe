"""Procedural and synthetic 3D mesh fixtures for fast hermetic testing."""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from harness.doctor import find_blender_binary


# Standard 1x1 transparent PNG data URI
SAMPLE_PNG_DATA_URI = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# Standard SVG decal data URI
SAMPLE_SVG_DATA_URI = (
    "data:image/svg+xml;utf8,"
    "%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%20100%20100%22%3E"
    "%3Ccircle%20cx%3D%2250%22%20cy%3D%2250%22%20r%3D%2240%22%20fill%3D%22%23ff3366%22/%3E"
    "%3C/svg%3E"
)


def sample_sticker_config(
    sticker_id: str = "sticker_001",
    image_url: str = SAMPLE_SVG_DATA_URI,
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: float = 0.25,
    target_mesh: str | None = None,
) -> dict[str, Any]:
    """Generate a single sticker specification."""
    return {
        "id": sticker_id,
        "type": "image",
        "imageUrl": image_url,
        "position": position or [0.0, 0.05, 0.0],
        "rotation": rotation or [0.0, 0.0, 0.0],
        "normal": [0.0, 1.0, 0.0],
        "scale": scale,
        "targetMeshName": target_mesh,
    }


def sample_text_config(
    text_id: str = "text_001",
    value: str = "KUS-AI",
    font: str = "Arial",
    color: str = "#FF0055",
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: float = 0.3,
) -> dict[str, Any]:
    """Generate a single text layer specification."""
    return {
        "id": text_id,
        "value": value,
        "font": font,
        "color": color,
        "position": position or [0.0, 0.05, 0.0],
        "rotation": rotation or [0.0, 0.0, 0.0],
        "normal": [0.0, 1.0, 0.0],
        "scale": scale,
    }


def build_design_payload(
    stickers: list[dict[str, Any]] | None = None,
    texts: list[dict[str, Any]] | None = None,
    base_color: str = "#ffffff",
    roughness: float = 1.0,
    metallic: float = 0.0,
) -> dict[str, Any]:
    """Build a complete design config payload."""
    return {
        "stickers": stickers if stickers is not None else [sample_sticker_config()],
        "texts": texts if texts is not None else [],
        "baseColor": base_color,
        "material": {
            "roughness": roughness,
            "metallic": metallic,
        },
    }


def generate_curved_test_mesh(output_path: Path, blender_bin: Optional[Path] = None) -> Path:
    """Generate a minimal curved surface mesh (GLB) via headless Blender.

    This generates a 100-poly curved mesh with UVs and an assigned material,
    perfect for rapid decal projection tests without loading 5MB+ files.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    binary = blender_bin or find_blender_binary()
    if not binary:
        raise RuntimeError("Blender executable is required to generate procedural test mesh.")

    python_expr = f"""
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10, size=1.0)
grid = bpy.context.active_object
grid.name = "shoe_upper"

# Apply slight curvature
for v in grid.data.vertices:
    x = v.co.x
    y = v.co.y
    v.co.z = 0.15 * (1.0 - (x*x + y*y))

# Add a default Principled BSDF material
mat = bpy.data.materials.new(name="ShoeMaterial")
mat.use_nodes = True
grid.data.materials.append(mat)

# Export to GLB
bpy.ops.export_scene.gltf(
    filepath=r"{str(output_path)}",
    export_format="GLB",
    use_selection=True,
    export_materials="EXPORT"
)
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as script_file:
        script_file.write(python_expr)
        script_file_path = Path(script_file.name)

    try:
        cmd = [
            str(binary),
            "--background",
            "--factory-startup",
            "--python",
            str(script_file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0 or not output_path.is_file():
            raise RuntimeError(
                f"Failed to generate procedural test mesh (exit code {result.returncode}):\n{result.stderr}\n{result.stdout}"
            )
    finally:
        if script_file_path.is_file():
            script_file_path.unlink()

    return output_path
