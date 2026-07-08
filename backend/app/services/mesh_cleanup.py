from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.path_safety import safe_child_path
from app.services.blender_service import BlenderService
from app.services.command_runner import CommandRunner
from app.services.placeholders import PLACEHOLDER_PNG


@dataclass(frozen=True)
class MeshCleanupOptions:
    target_max_dimension: float
    decimate_triangle_threshold: int
    decimate_ratio: float

    @classmethod
    def from_settings(cls) -> "MeshCleanupOptions":
        settings = get_settings()
        return cls(
            target_max_dimension=settings.mesh_cleanup_target_max_dimension,
            decimate_triangle_threshold=settings.mesh_cleanup_decimate_triangle_threshold,
            decimate_ratio=settings.mesh_cleanup_decimate_ratio,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "targetMaxDimension": self.target_max_dimension,
            "decimateTriangleThreshold": self.decimate_triangle_threshold,
            "decimateRatio": self.decimate_ratio,
        }


@dataclass(frozen=True)
class MeshCleanupReport:
    editor_ready: bool
    editor_ready_score: int
    mesh_object_count: int
    bounding_box: dict[str, Any]
    normalized_scale: float
    triangle_count_before: int
    triangle_count_after: int
    cleanup_warnings: list[str]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "MeshCleanupReport":
        return cls(
            editor_ready=bool(payload.get("editorReady", False)),
            editor_ready_score=int(payload.get("editorReadyScore", 0)),
            mesh_object_count=int(payload.get("meshObjectCount", 0)),
            bounding_box=dict(payload.get("boundingBox") or {}),
            normalized_scale=float(payload.get("normalizedScale", 1.0)),
            triangle_count_before=int(payload.get("triangleCountBefore", 0)),
            triangle_count_after=int(payload.get("triangleCountAfter", 0)),
            cleanup_warnings=[
                str(item) for item in payload.get("cleanupWarnings", []) if str(item).strip()
            ],
        )

    def to_quality_fields(self) -> dict[str, Any]:
        return {
            "editorReady": self.editor_ready,
            "editorReadyScore": self.editor_ready_score,
            "meshObjectCount": self.mesh_object_count,
            "boundingBox": self.bounding_box,
            "normalizedScale": self.normalized_scale,
            "triangleCountBefore": self.triangle_count_before,
            "triangleCountAfter": self.triangle_count_after,
            "cleanupWarnings": self.cleanup_warnings,
        }


class MeshCleanupService:
    def __init__(
        self,
        blender: BlenderService | None = None,
        runner: CommandRunner | None = None,
        options: MeshCleanupOptions | None = None,
    ) -> None:
        self.settings = get_settings()
        self.blender = blender or BlenderService()
        self.runner = runner or CommandRunner()
        self.options = options or MeshCleanupOptions.from_settings()

    def cleanup(
        self,
        source_model: Path,
        output_dir: Path,
        *,
        texture_path: Path | None = None,
        log_path: Path | None = None,
        options: MeshCleanupOptions | None = None,
    ) -> MeshCleanupReport:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir = output_dir.resolve()
        work_dir = safe_child_path(output_dir, "_mesh_cleanup", label="mesh cleanup work directory")
        work_dir.mkdir(parents=True, exist_ok=True)
        script_path = safe_child_path(work_dir, "editor_ready_cleanup.py", label="cleanup script path")
        options_path = safe_child_path(work_dir, "mesh_cleanup_options.json", label="cleanup options path")
        report_path = safe_child_path(work_dir, "mesh_cleanup_report.json", label="cleanup report path")
        active_options = options or self.options

        self._write_cleanup_script(script_path)
        options_path.write_text(json.dumps(active_options.to_payload(), indent=2), encoding="utf-8")

        command = [
            self.blender.require_available(),
            "--background",
            "--python",
            str(script_path),
            "--",
            str(source_model),
            str(output_dir),
            str(report_path),
            str(options_path),
            str(texture_path or ""),
        ]
        result = self.runner.run(
            command,
            log_path=log_path or work_dir / "mesh_cleanup.log",
            cwd=output_dir,
            timeout=self.settings.reconstruction_command_timeout_seconds,
        )
        if not result.ok:
            message = result.stderr.strip() or result.stdout.strip() or "Blender mesh cleanup failed."
            raise RuntimeError(f"Blender mesh cleanup failed: {message[-1200:]}")

        self._ensure_canonical_files(output_dir, texture_path)
        if not report_path.is_file():
            raise RuntimeError("Blender mesh cleanup did not create mesh cleanup report.")
        return MeshCleanupReport.from_payload(json.loads(report_path.read_text(encoding="utf-8")))

    def _ensure_canonical_files(self, output_dir: Path, texture_path: Path | None) -> None:
        output_dir = output_dir.resolve()
        for name in ["shoe_preview.glb", "shoe.obj"]:
            canonical_path = safe_child_path(output_dir, name, label=f"{name} path")
            if not canonical_path.is_file():
                raise RuntimeError(f"Blender mesh cleanup did not create {name}.")

        mtl_path = safe_child_path(output_dir, "shoe.mtl", label="material output path")
        texture_output = safe_child_path(output_dir, "shoe_texture.png", label="texture output path")
        if not texture_output.is_file():
            if texture_path and texture_path.is_file() and texture_path.suffix.lower() == ".png":
                shutil.copyfile(texture_path, texture_output)
            else:
                texture_output.write_bytes(PLACEHOLDER_PNG)

        if mtl_path.is_file():
            self._rewrite_mtl_texture(mtl_path)
        else:
            mtl_path.write_text(
                "newmtl editor_ready_material\n"
                "Kd 1.000000 1.000000 1.000000\n"
                "map_Kd shoe_texture.png\n",
                encoding="utf-8",
            )

    def _rewrite_mtl_texture(self, mtl_path: Path) -> None:
        lines = mtl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        rewritten = []
        replaced = False
        for line in lines:
            if line.strip().startswith("map_Kd "):
                rewritten.append("map_Kd shoe_texture.png")
                replaced = True
            else:
                rewritten.append(line)
        if not replaced:
            rewritten.append("map_Kd shoe_texture.png")
        mtl_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    def _write_cleanup_script(self, path: Path) -> None:
        path.write_text(
            r'''
import json
import pathlib
import sys
import traceback

import bpy
import mathutils


def patch_numpy_compat():
    try:
        import numpy as np
    except Exception:
        return

    aliases = {
        "bool": bool,
        "int": int,
        "float": float,
        "complex": complex,
        "object": object,
        "str": str,
    }
    for name, value in aliases.items():
        if name not in np.__dict__:
            setattr(np, name, value)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_model(path):
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        patch_numpy_compat()
        bpy.ops.import_scene.gltf(filepath=str(path))
        return
    if suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
        return
    raise RuntimeError(f"Unsupported model extension for mesh cleanup: {suffix}")


def export_obj(path):
    if hasattr(bpy.ops.wm, "obj_export"):
        try:
            bpy.ops.wm.obj_export(filepath=str(path), export_materials=True, path_mode="COPY")
        except TypeError:
            bpy.ops.wm.obj_export(filepath=str(path), export_materials=True)
    else:
        bpy.ops.export_scene.obj(filepath=str(path), use_materials=True, path_mode="COPY")


def mesh_objects():
    return [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.data and len(obj.data.vertices) > 0 and len(obj.data.polygons) > 0
    ]


def remove_non_mesh_objects():
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)


def remove_empty_mesh_objects():
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH" and (
            not obj.data or len(obj.data.vertices) == 0 or len(obj.data.polygons) == 0
        ):
            bpy.data.objects.remove(obj, do_unlink=True)


def triangle_count(meshes):
    total = 0
    for obj in meshes:
        total += sum(max(1, len(poly.vertices) - 2) for poly in obj.data.polygons)
    return total


def scene_bounds(meshes):
    min_corner = mathutils.Vector((float("inf"), float("inf"), float("inf")))
    max_corner = mathutils.Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in meshes:
        obj.update_from_editmode()
        obj.update_tag()
        for corner in obj.bound_box:
            world = obj.matrix_world @ mathutils.Vector(corner)
            min_corner.x = min(min_corner.x, world.x)
            min_corner.y = min(min_corner.y, world.y)
            min_corner.z = min(min_corner.z, world.z)
            max_corner.x = max(max_corner.x, world.x)
            max_corner.y = max(max_corner.y, world.y)
            max_corner.z = max(max_corner.z, world.z)
    size = max_corner - min_corner
    return {
        "min": [min_corner.x, min_corner.y, min_corner.z],
        "max": [max_corner.x, max_corner.y, max_corner.z],
        "size": [size.x, size.y, size.z],
        "center": [(min_corner.x + max_corner.x) / 2, (min_corner.y + max_corner.y) / 2, (min_corner.z + max_corner.z) / 2],
        "maxDimension": max(size.x, size.y, size.z),
    }


def clean_mesh_geometry(obj, warnings):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        try:
            bpy.ops.mesh.delete_loose()
        except Exception:
            pass
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception as exc:
        warnings.append(f"Mesh geometry cleanup skipped for {obj.name}: {exc}")
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass


def apply_decimation(meshes, threshold, max_ratio, warnings):
    before = triangle_count(meshes)
    if threshold <= 0 or before <= threshold:
        return
    ratio = max(0.05, min(float(max_ratio), threshold / max(before, 1)))
    for obj in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new("editor_ready_decimate", "DECIMATE")
        modifier.ratio = ratio
        try:
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        except Exception as exc:
            warnings.append(f"Decimation skipped for {obj.name}: {exc}")
            obj.modifiers.remove(modifier)
    warnings.append(f"Triangle count exceeded editor budget and was decimated with ratio {ratio:.3f}.")


def normalize_scene(meshes, target_max_dimension):
    bounds = scene_bounds(meshes)
    extent = float(bounds["maxDimension"])
    if extent <= 0.000001:
        raise RuntimeError("Imported mesh bounds are too small to normalize.")
    center = mathutils.Vector(bounds["center"])
    scale = float(target_max_dimension) / extent
    transform = mathutils.Matrix.Scale(scale, 4) @ mathutils.Matrix.Translation(-center)
    for obj in meshes:
        obj.matrix_world = transform @ obj.matrix_world
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return scale, bounds


def save_texture(texture_path, output_path, warnings):
    source = pathlib.Path(texture_path) if texture_path else None
    if source and source.is_file():
        try:
            image = bpy.data.images.load(str(source), check_existing=True)
            image.filepath_raw = str(output_path)
            image.file_format = "PNG"
            image.save()
            return True
        except Exception as exc:
            warnings.append(f"Source texture could not be saved as PNG: {exc}")
    for image in bpy.data.images:
        try:
            width, height = image.size
        except Exception:
            continue
        if width <= 1 or height <= 1:
            continue
        try:
            image.filepath_raw = str(output_path)
            image.file_format = "PNG"
            image.save()
            return True
        except Exception:
            continue
    warnings.append("No reusable source texture was found; placeholder texture will be used.")
    return False


def score_report(warnings, triangle_count_after, threshold):
    score = 100
    score -= min(40, len(warnings) * 10)
    if threshold > 0 and triangle_count_after > threshold:
        score -= 15
    return max(0, min(100, score))


try:
    argv = sys.argv[sys.argv.index("--") + 1:]
    source_model = pathlib.Path(argv[0])
    output_dir = pathlib.Path(argv[1])
    report_path = pathlib.Path(argv[2])
    options_path = pathlib.Path(argv[3])
    texture_path = argv[4] if len(argv) > 4 else ""
    options = json.loads(options_path.read_text(encoding="utf-8"))
    warnings = []

    output_dir.mkdir(parents=True, exist_ok=True)
    clear_scene()
    import_model(source_model)
    remove_non_mesh_objects()
    remove_empty_mesh_objects()

    meshes = mesh_objects()
    if not meshes:
        raise RuntimeError("Imported model contains no usable mesh objects.")

    mesh_count = len(meshes)
    triangles_before = triangle_count(meshes)
    for mesh in meshes:
        clean_mesh_geometry(mesh, warnings)
    apply_decimation(
        meshes,
        int(options.get("decimateTriangleThreshold", 250000)),
        float(options.get("decimateRatio", 0.75)),
        warnings,
    )
    normalized_scale, bounds_before = normalize_scene(
        meshes,
        float(options.get("targetMaxDimension", 2.4)),
    )
    bpy.context.view_layer.update()
    bounds_after = scene_bounds(meshes)
    triangles_after = triangle_count(meshes)
    texture_saved = save_texture(texture_path, output_dir / "shoe_texture.png", warnings)

    bpy.ops.export_scene.gltf(filepath=str(output_dir / "shoe_preview.glb"), export_format="GLB")
    export_obj(output_dir / "shoe.obj")

    score = score_report(
        warnings,
        triangles_after,
        int(options.get("decimateTriangleThreshold", 250000)),
    )
    report = {
        "editorReady": score >= 60 and mesh_count > 0,
        "editorReadyScore": score,
        "meshObjectCount": mesh_count,
        "boundingBox": {
            "before": bounds_before,
            "after": bounds_after,
        },
        "normalizedScale": normalized_scale,
        "triangleCountBefore": triangles_before,
        "triangleCountAfter": triangles_after,
        "textureSaved": texture_saved,
        "cleanupWarnings": warnings,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
except Exception:
    traceback.print_exc()
    sys.exit(1)
'''.lstrip(),
            encoding="utf-8",
        )
