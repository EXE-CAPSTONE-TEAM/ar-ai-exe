from __future__ import annotations

import json
import shutil
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

    def is_available(self) -> bool:
        return self.blender.is_available()

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
        # The script imports the shared crop maths (axis + Euler-order conversion) from beside itself.
        shutil.copyfile(Path(__file__).with_name("crop_math.py"), work_dir / "crop_math.py")
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import crop_math  # noqa: E402  (copied next to this script by CropBakeService)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def mesh_objects():
    return [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.data and len(obj.data.polygons) > 0
    ]


def world_corners(objects):
    for obj in objects:
        for corner in obj.bound_box:
            world = obj.matrix_world @ mathutils.Vector(corner)
            yield (world.x, world.y, world.z)


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

    # The crop box is authored in glTF (Y-up) space with three.js Euler order; crop_math converts
    # it to Blender's Z-up world as an explicit matrix (see crop_math module docstring).
    bounds_center, bounds_size = crop_math.gltf_bounds(world_corners(objects))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, 0.0, 0.0))
    cutter = bpy.context.active_object
    cutter.name = "kiri_crop_bounds"
    cutter.matrix_world = mathutils.Matrix(crop_math.cutter_matrix(crop, bounds_center, bounds_size))
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
