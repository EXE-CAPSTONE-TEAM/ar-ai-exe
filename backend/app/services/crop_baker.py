from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.schemas.scan import CropBox
from app.services.blender_service import BlenderService
from app.services.command_runner import CommandRunner


class CropBakeService:
    def __init__(
        self,
        blender: BlenderService | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.settings = get_settings()
        self.blender = blender or BlenderService()
        self.runner = runner or CommandRunner()

    def bake(self, source_glb: Path, output_glb: Path, crop_box: CropBox) -> None:
        work_dir = output_glb.parent / "_crop_bake"
        work_dir.mkdir(parents=True, exist_ok=True)
        crop_path = work_dir / "crop_box.json"
        script_path = work_dir / "crop_glb.py"
        crop_path.write_text(
            json.dumps(crop_box.model_dump(by_alias=True), indent=2),
            encoding="utf-8",
        )
        self._write_script(script_path)
        result = self.runner.run(
            [
                self.blender.require_available(),
                "--background",
                "--python",
                str(script_path),
                "--",
                str(source_glb.resolve()),
                str(output_glb.resolve()),
                str(crop_path.resolve()),
            ],
            log_path=work_dir / "crop_bake.log",
            cwd=work_dir,
            timeout=self.settings.reconstruction_command_timeout_seconds,
        )
        if not result.ok or not output_glb.is_file():
            message = result.stderr.strip() or result.stdout.strip() or "Blender crop bake failed."
            raise RuntimeError(f"Blender crop bake failed: {message[-1200:]}")

    @staticmethod
    def _write_script(path: Path) -> None:
        path.write_text(
            r'''
import json
import math
import pathlib
import sys

import bpy
import mathutils


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def mesh_objects():
    return [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.data and len(obj.data.polygons) > 0
    ]


def scene_bounds(objects):
    minimum = mathutils.Vector((float("inf"), float("inf"), float("inf")))
    maximum = mathutils.Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in objects:
        for corner in obj.bound_box:
            world = obj.matrix_world @ mathutils.Vector(corner)
            minimum.x = min(minimum.x, world.x)
            minimum.y = min(minimum.y, world.y)
            minimum.z = min(minimum.z, world.z)
            maximum.x = max(maximum.x, world.x)
            maximum.y = max(maximum.y, world.y)
            maximum.z = max(maximum.z, world.z)
    return minimum, maximum


def main():
    source_path = pathlib.Path(sys.argv[-3]).resolve()
    output_path = pathlib.Path(sys.argv[-2]).resolve()
    crop_path = pathlib.Path(sys.argv[-1]).resolve()
    crop = json.loads(crop_path.read_text(encoding="utf-8"))

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source_path))
    objects = mesh_objects()
    if not objects:
        raise RuntimeError("Source GLB does not contain a mesh.")

    minimum, maximum = scene_bounds(objects)
    bounds_size = maximum - minimum
    bounds_center = (minimum + maximum) * 0.5
    center = crop["center"]
    size = crop["size"]
    rotation = crop.get("rotation") or {"x": 0, "y": 0, "z": 0}

    crop_center = bounds_center + mathutils.Vector((
        center["x"] * bounds_size.x,
        center["y"] * bounds_size.y,
        center["z"] * bounds_size.z,
    ))
    crop_size = mathutils.Vector((
        max(bounds_size.x * size["x"], 0.000001),
        max(bounds_size.y * size["y"], 0.000001),
        max(bounds_size.z * size["z"], 0.000001),
    ))

    bpy.ops.mesh.primitive_cube_add(size=1, location=crop_center)
    cutter = bpy.context.active_object
    cutter.name = "kiri_crop_bounds"
    cutter.dimensions = crop_size
    cutter.rotation_euler = tuple(math.radians(rotation[axis]) for axis in ("x", "y", "z"))
    bpy.context.view_layer.objects.active = cutter
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    for obj in list(objects):
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new(name="Kiri crop", type="BOOLEAN")
        modifier.operation = "INTERSECT"
        modifier.solver = "EXACT"
        modifier.object = cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    bpy.data.objects.remove(cutter, do_unlink=True)
    for obj in list(mesh_objects()):
        if len(obj.data.polygons) == 0:
            bpy.data.objects.remove(obj, do_unlink=True)
    if not mesh_objects():
        raise RuntimeError("Crop box removed the entire model.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        export_apply=True,
        export_materials="EXPORT",
    )


if __name__ == "__main__":
    main()
'''.strip()
            + "\n",
            encoding="utf-8",
        )
