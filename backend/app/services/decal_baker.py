from __future__ import annotations

import base64
import html
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote_to_bytes

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.blender_service import BlenderService
from app.services.command_runner import CommandRunner


DATA_URI_RE = re.compile(r"^data:(?P<mime>image/(?:png|jpe?g|svg\+xml))(?P<meta>[^,]*),(?P<data>.*)$", re.I | re.S)
MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/svg+xml": ".svg",
}
MAX_STICKERS = 50
MAX_STICKER_BYTES = 5 * 1024 * 1024
MAX_TEXT_LENGTH = 80
ImageAssetResolver = Callable[[str], tuple[bytes, str]]


class DecalBakeService:
    def __init__(self, asset_resolver: ImageAssetResolver | None = None) -> None:
        self.settings = get_settings()
        self.blender = BlenderService()
        self.runner = CommandRunner()
        self.asset_resolver = asset_resolver

    def bake(self, source_glb: Path, output_dir: Path, design_config: dict[str, Any]) -> bool:
        decals = self._prepare_decals(output_dir, design_config)
        if not decals:
            return False

        work_dir = output_dir / "_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        source_copy = work_dir / "source.glb"
        shutil.copyfile(source_glb, source_copy)

        manifest_path = work_dir / "decal_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "decals": decals,
                    "material": self._prepare_material(design_config),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        script_path = work_dir / "apply_decals.py"
        self._write_blender_script(script_path)

        try:
            blender_bin = self.blender.require_available()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        command = [
            blender_bin,
            "--background",
            "--python",
            str(script_path),
            "--",
            str(source_copy),
            str(output_dir),
            str(manifest_path),
        ]
        result = self.runner.run(
            command,
            log_path=work_dir / "decal_bake.log",
            cwd=output_dir,
            timeout=self.settings.reconstruction_command_timeout_seconds,
        )
        if not result.ok:
            message = result.stderr.strip() or result.stdout.strip() or "Blender decal bake failed."
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Blender decal bake failed: {message[-1200:]}",
            )

        for name in ["final_shoe.glb", "final_shoe.obj", "final_shoe.mtl"]:
            if not (output_dir / name).is_file():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Blender decal bake did not create {name}.",
                )
        return True

    def _prepare_decals(self, output_dir: Path, design_config: dict[str, Any]) -> list[dict[str, Any]]:
        decals = [
            *self._prepare_stickers(output_dir, design_config),
            *self._prepare_texts(output_dir, design_config),
        ]
        if len(decals) > MAX_STICKERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Design cannot export more than {MAX_STICKERS} decal layers.",
            )
        return decals

    def _prepare_material(self, design_config: dict[str, Any]) -> dict[str, Any]:
        raw_material = design_config.get("material", {})
        material = raw_material if isinstance(raw_material, dict) else {}
        return {
            "baseColor": self._safe_color(str(design_config.get("baseColor") or "#ffffff")),
            "roughness": self._number(material.get("roughness"), 1.0, minimum=0.0, maximum=1.0),
            "metallic": self._number(material.get("metallic"), 0.0, minimum=0.0, maximum=1.0),
        }

    def _prepare_stickers(self, output_dir: Path, design_config: dict[str, Any]) -> list[dict[str, Any]]:
        raw_stickers = design_config.get("stickers", [])
        if not isinstance(raw_stickers, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design stickers must be an array.",
            )
        if len(raw_stickers) > MAX_STICKERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Design cannot export more than {MAX_STICKERS} stickers.",
            )

        stickers_dir = output_dir / "stickers"
        prepared: list[dict[str, Any]] = []
        for index, sticker in enumerate(raw_stickers, start=1):
            if not isinstance(sticker, dict):
                continue
            sticker_id = self._safe_name(str(sticker.get("id") or f"sticker_{index:03d}"))
            asset_id = self._asset_id(sticker.get("assetId") or sticker.get("asset_id"))
            if asset_id:
                image_path, mime_type = self._write_asset_image(
                    asset_id,
                    stickers_dir,
                    f"{index:03d}_{sticker_id}",
                )
            else:
                image_url = sticker.get("imageUrl")
                if not isinstance(image_url, str) or not image_url.strip():
                    continue
                image_path, mime_type = self._write_sticker_image(
                    image_url,
                    stickers_dir,
                    f"{index:03d}_{sticker_id}",
                )
            scale = self._number(sticker.get("scale"), 0.2, minimum=0.01, maximum=10.0)
            width = self._number(sticker.get("width"), scale, minimum=0.01, maximum=10.0)
            height = self._number(sticker.get("height"), scale, minimum=0.01, maximum=10.0)
            normal = self._normal(sticker.get("normal"))
            decal = {
                "id": sticker_id,
                "kind": "image",
                "imagePath": str(image_path),
                "mimeType": mime_type,
                "position": self._vec3(sticker.get("position"), [0.0, 0.0, 0.0]),
                "rotation": self._vec3(sticker.get("rotation"), [0.0, 0.0, 0.0]),
                "targetMeshName": sticker.get("targetMeshName") or "",
                "width": width,
                "height": height,
                "offset": self._number(sticker.get("offset"), 0.004, minimum=0.0, maximum=0.1),
                "projectionDepth": self._number(
                    sticker.get("projectionDepth"),
                    max(scale * 1.5, 0.05),
                    minimum=0.01,
                    maximum=10.0,
                ),
                "subdivisions": int(
                    self._number(sticker.get("subdivisions"), 32, minimum=4, maximum=128)
                ),
            }
            if normal:
                decal["normal"] = normal
            prepared.append(
                decal
            )
        return prepared

    def _prepare_texts(self, output_dir: Path, design_config: dict[str, Any]) -> list[dict[str, Any]]:
        raw_texts = design_config.get("texts", [])
        if not isinstance(raw_texts, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design texts must be an array.",
            )
        if len(raw_texts) > MAX_STICKERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Design cannot export more than {MAX_STICKERS} text layers.",
            )

        stickers_dir = output_dir / "stickers"
        prepared: list[dict[str, Any]] = []
        for index, text_layer in enumerate(raw_texts, start=1):
            if not isinstance(text_layer, dict):
                continue
            value = str(text_layer.get("value") or "").strip()
            if not value:
                continue
            if len(value) > MAX_TEXT_LENGTH:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Text decal exceeds the {MAX_TEXT_LENGTH} character limit.",
                )

            text_id = self._safe_name(str(text_layer.get("id") or f"text_{index:03d}"))
            scale = self._number(text_layer.get("scale"), 0.2, minimum=0.01, maximum=10.0)
            width = self._number(
                text_layer.get("width"),
                max(scale * max(len(value) * 0.62, 1.0), 0.01),
                minimum=0.01,
                maximum=10.0,
            )
            height = self._number(text_layer.get("height"), scale, minimum=0.01, maximum=10.0)
            color = self._safe_color(str(text_layer.get("color") or "#ffffff"))
            font = self._safe_font(str(text_layer.get("font") or "Arial"))
            render_asset_id = self._asset_id(
                text_layer.get("renderAssetId") or text_layer.get("render_asset_id")
            )
            normal = self._normal(text_layer.get("normal"))

            if render_asset_id:
                image_path, mime_type = self._write_asset_image(
                    render_asset_id,
                    stickers_dir,
                    f"{index:03d}_{text_id}",
                )
                decal = {
                    "id": text_id,
                    "kind": "image",
                    "imagePath": str(image_path),
                    "mimeType": mime_type,
                    "position": self._vec3(text_layer.get("position"), [0.0, 0.0, 0.0]),
                    "rotation": self._vec3(text_layer.get("rotation"), [0.0, 0.0, 0.0]),
                    "targetMeshName": text_layer.get("targetMeshName") or "",
                    "width": width,
                    "height": height,
                    "offset": self._number(text_layer.get("offset"), 0.004, minimum=0.0, maximum=0.1),
                    "projectionDepth": self._number(
                        text_layer.get("projectionDepth"),
                        max(scale * 1.5, 0.05),
                        minimum=0.01,
                        maximum=10.0,
                    ),
                    "subdivisions": int(
                        self._number(text_layer.get("subdivisions"), 32, minimum=4, maximum=128)
                    ),
                }
                if normal:
                    decal["normal"] = normal
                prepared.append(decal)
                continue

            image_path = self._write_text_svg(value, font, color, stickers_dir, f"{index:03d}_{text_id}")

            decal = {
                "id": text_id,
                "kind": "text",
                "imagePath": str(image_path),
                "mimeType": "image/svg+xml",
                "text": value,
                "font": font,
                "color": color,
                "position": self._vec3(text_layer.get("position"), [0.0, 0.0, 0.0]),
                "rotation": self._vec3(text_layer.get("rotation"), [0.0, 0.0, 0.0]),
                "targetMeshName": text_layer.get("targetMeshName") or "",
                "width": width,
                "height": height,
                "offset": self._number(text_layer.get("offset"), 0.004, minimum=0.0, maximum=0.1),
                "projectionDepth": self._number(
                    text_layer.get("projectionDepth"),
                    max(scale * 1.5, 0.05),
                    minimum=0.01,
                    maximum=10.0,
                ),
                "subdivisions": int(
                    self._number(text_layer.get("subdivisions"), 32, minimum=4, maximum=128)
                ),
            }
            if normal:
                decal["normal"] = normal
            prepared.append(decal)
        return prepared

    def _write_sticker_image(self, image_url: str, output_dir: Path, basename: str) -> tuple[Path, str]:
        match = DATA_URI_RE.match(image_url.strip())
        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sticker images must be embedded PNG, JPEG, or SVG data URIs.",
            )

        mime_type = match.group("mime").lower()
        extension = MIME_EXTENSIONS[mime_type]
        meta = match.group("meta").lower()
        payload = match.group("data")
        try:
            data = (
                base64.b64decode(payload, validate=True)
                if ";base64" in meta
                else unquote_to_bytes(payload)
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sticker data URI could not be decoded.",
            ) from exc

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sticker image is empty.",
            )
        if len(data) > MAX_STICKER_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Sticker image exceeds the 5 MB export limit.",
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"{basename}{extension}"
        image_path.write_bytes(data)
        return image_path, mime_type

    def _write_asset_image(self, asset_id: str, output_dir: Path, basename: str) -> tuple[Path, str]:
        resolver = getattr(self, "asset_resolver", None)
        if resolver is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design asset images cannot be resolved for this export.",
            )

        data, content_type = resolver(asset_id)
        mime_type = content_type.lower()
        if mime_type not in MIME_EXTENSIONS or mime_type == "image/svg+xml":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design asset images must be PNG or JPEG.",
            )
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design asset image is empty.",
            )
        if len(data) > MAX_STICKER_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Design asset image exceeds the 5 MB export limit.",
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"{basename}{MIME_EXTENSIONS[mime_type]}"
        image_path.write_bytes(data)
        return image_path, mime_type

    def _write_text_svg(
        self,
        value: str,
        font: str,
        color: str,
        output_dir: Path,
        basename: str,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"{basename}.svg"
        aspect = max(len(value) * 0.62, 1.0)
        width = int(512 * aspect)
        escaped_text = html.escape(value, quote=False)
        escaped_font = html.escape(font, quote=True)
        image_path.write_text(
            (
                '<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="512" '
                'viewBox="0 0 {width} 512">'
                '<rect width="100%" height="100%" fill="none"/>'
                '<text x="50%" y="50%" fill="{color}" font-family="{font}" '
                'font-size="300" font-weight="700" text-anchor="middle" '
                'dominant-baseline="central">{text}</text>'
                "</svg>"
            ).format(width=width, color=color, font=escaped_font, text=escaped_text),
            encoding="utf-8",
        )
        return image_path

    def _safe_name(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")[:80] or "sticker"

    def _safe_color(self, value: str) -> str:
        color = value.strip()
        return color if re.fullmatch(r"#[0-9A-Fa-f]{6}", color) else "#ffffff"

    def _safe_font(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 ._-]+", "", value).strip()
        return cleaned[:80] or "Arial"

    def _asset_id(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    def _number(self, value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return min(maximum, max(minimum, number))

    def _vec3(self, value: Any, default: list[float]) -> list[float]:
        if not isinstance(value, list | tuple) or len(value) != 3:
            return default
        return [self._number(item, fallback, minimum=-100.0, maximum=100.0) for item, fallback in zip(value, default)]

    def _normal(self, value: Any) -> list[float] | None:
        if not isinstance(value, list | tuple) or len(value) != 3:
            return None
        vector = [self._number(item, 0.0, minimum=-1.0, maximum=1.0) for item in value]
        length = math.sqrt(sum(item * item for item in vector))
        if length <= 0.000001:
            return None
        return [item / length for item in vector]

    def _write_blender_script(self, path: Path) -> None:
        path.write_text(
            r'''
import json
import math
import pathlib
import sys
import traceback

import bpy
import mathutils
from mathutils.bvhtree import BVHTree


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
    patch_numpy_compat()
    bpy.ops.import_scene.gltf(filepath=str(path))


def export_obj(path):
    if hasattr(bpy.ops.wm, "obj_export"):
        try:
            bpy.ops.wm.obj_export(
                filepath=str(path),
                export_materials=True,
                path_mode="COPY",
            )
        except TypeError:
            bpy.ops.wm.obj_export(filepath=str(path), export_materials=True)
    else:
        bpy.ops.export_scene.obj(
            filepath=str(path),
            use_materials=True,
            path_mode="COPY",
        )


def mesh_objects():
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def target_mesh_candidates():
    candidates = [
        obj for obj in mesh_objects()
        if not obj.name.startswith("decal_")
        and not obj.name.startswith("svg_decal_")
        and not obj.name.startswith("text_decal_")
    ]
    if not candidates:
        raise RuntimeError("Imported model contains no target mesh.")
    return candidates


def find_target_meshes(target_name):
    candidates = target_mesh_candidates()
    if target_name:
        matches = []
        for obj in candidates:
            if obj.name == target_name or obj.data.name == target_name:
                matches.append(obj)
            if obj.name.startswith(target_name):
                matches.append(obj)
        if matches:
            return matches
    return candidates


def set_optional(obj, name, value):
    try:
        setattr(obj, name, value)
    except Exception:
        pass


def create_image_material(decal):
    image = bpy.data.images.load(decal["imagePath"], check_existing=True)
    material = bpy.data.materials.new(f"decal_{decal['id']}_material")
    material.use_nodes = True
    material.use_backface_culling = False
    material.blend_method = "BLEND"
    material.diffuse_color = (1, 1, 1, 1)
    set_optional(material, "show_transparent_back", True)

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    texture_node = nodes.new("ShaderNodeTexImage")
    texture_node.image = image
    if bsdf:
        links.new(texture_node.outputs["Color"], bsdf.inputs["Base Color"])
        if "Alpha" in bsdf.inputs:
            links.new(texture_node.outputs["Alpha"], bsdf.inputs["Alpha"])
            bsdf.inputs["Alpha"].default_value = 1.0
    return material


def parse_hex_color(value):
    text = str(value or "#ffffff").lstrip("#")
    if len(text) != 6:
        text = "ffffff"
    try:
        red = int(text[0:2], 16) / 255
        green = int(text[2:4], 16) / 255
        blue = int(text[4:6], 16) / 255
    except ValueError:
        red, green, blue = 1, 1, 1
    return (red, green, blue, 1)


def create_design_base_material(color, roughness, metallic):
    material = bpy.data.materials.new("design_base_material")
    material.use_nodes = True
    apply_material_settings(material, color, roughness, metallic)
    return material


def apply_material_settings(material, color, roughness, metallic):
    material.use_backface_culling = False
    material.diffuse_color = color
    if not material.use_nodes:
        material.use_nodes = True

    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        base_color = bsdf.inputs.get("Base Color")
        if base_color and not base_color.links:
            base_color.default_value = color
        roughness_input = bsdf.inputs.get("Roughness")
        if roughness_input:
            roughness_input.default_value = roughness
        metallic_input = bsdf.inputs.get("Metallic")
        if metallic_input:
            metallic_input.default_value = metallic


def apply_design_material(material_config):
    color = parse_hex_color(material_config.get("baseColor"))
    roughness = max(0.0, min(1.0, float(material_config.get("roughness", 1.0))))
    metallic = max(0.0, min(1.0, float(material_config.get("metallic", 0.0))))

    for target in target_mesh_candidates():
        materials = [material for material in target.data.materials if material]
        if not materials:
            target.data.materials.append(create_design_base_material(color, roughness, metallic))
            for polygon in target.data.polygons:
                polygon.material_index = 0
            continue

        for material in materials:
            apply_material_settings(material, color, roughness, metallic)

        slot_count = len(target.data.materials)
        for polygon in target.data.polygons:
            if polygon.material_index >= slot_count or not target.data.materials[polygon.material_index]:
                polygon.material_index = 0


def create_solid_material(decal):
    color = parse_hex_color(decal.get("color"))
    material = bpy.data.materials.new(f"decal_{decal['id']}_material")
    material.use_nodes = True
    material.use_backface_culling = False
    material.diffuse_color = color
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = color[3]
    return material


def create_grid_object(decal):
    cuts = max(4, min(128, int(decal["subdivisions"])))
    width = float(decal["width"])
    height = float(decal["height"])
    vertices = []
    faces = []
    uvs = []

    for row in range(cuts + 1):
        v = row / cuts
        y = (v - 0.5) * height
        for col in range(cuts + 1):
            u = col / cuts
            x = (u - 0.5) * width
            vertices.append((x, y, 0.0))
            uvs.append((u, v))

    row_width = cuts + 1
    for row in range(cuts):
        for col in range(cuts):
            a = row * row_width + col
            b = a + 1
            c = a + row_width
            d = c + 1
            faces.append((a, b, d, c))

    mesh = bpy.data.meshes.new(f"decal_{decal['id']}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv_layer.data[loop_index].uv = uvs[vertex_index]

    obj = bpy.data.objects.new(f"decal_{decal['id']}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(create_image_material(decal))
    return obj


def import_svg_object(decal):
    try:
        bpy.ops.preferences.addon_enable(module="io_curve_svg")
    except Exception:
        pass

    before = set(bpy.context.scene.objects)
    bpy.ops.import_curve.svg(filepath=decal["imagePath"])
    imported = [obj for obj in bpy.context.scene.objects if obj not in before]
    if not imported:
        raise RuntimeError(f"SVG decal {decal['id']} imported no objects.")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in imported:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    bpy.ops.object.convert(target="MESH")
    converted = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if not converted:
        raise RuntimeError(f"SVG decal {decal['id']} converted no mesh.")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in converted:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = converted[0]
    if len(converted) > 1:
        bpy.ops.object.join()

    obj = bpy.context.view_layer.objects.active
    obj.name = f"svg_decal_{decal['id']}"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    normalize_svg_mesh(obj, float(decal["width"]), float(decal["height"]))
    return obj


def normalize_svg_mesh(obj, width, height):
    vertices = obj.data.vertices
    if not vertices:
        return

    xs = [vertex.co.x for vertex in vertices]
    ys = [vertex.co.y for vertex in vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    current_width = max(max_x - min_x, 0.0001)
    current_height = max(max_y - min_y, 0.0001)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    scale = min(width / current_width, height / current_height)

    for vertex in vertices:
        vertex.co.x = (vertex.co.x - center_x) * scale
        vertex.co.y = (vertex.co.y - center_y) * scale
        vertex.co.z = 0.0
    obj.data.update()


def create_text_object(decal):
    curve = bpy.data.curves.new(f"text_decal_{decal['id']}_curve", "FONT")
    curve.body = str(decal.get("text") or "")
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = 1.0
    curve.resolution_u = 12

    obj = bpy.data.objects.new(f"text_decal_{decal['id']}", curve)
    bpy.context.scene.collection.objects.link(obj)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    converted = bpy.context.view_layer.objects.active
    normalize_svg_mesh(converted, float(decal["width"]), float(decal["height"]))
    converted.data.materials.clear()
    converted.data.materials.append(create_solid_material(decal))
    return converted


def subdivide_mesh(obj, subdivisions):
    cuts = max(1, min(8, int(subdivisions) // 16))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.object.mode_set(mode="OBJECT")


def set_decal_transform(obj, decal):
    obj.location = gltf_vector_to_blender(decal["position"])
    obj.rotation_euler = gltf_rotation_to_blender(decal["rotation"])


def gltf_to_blender_matrix():
    return mathutils.Matrix.Rotation(1.5707963267948966, 4, "X")


def gltf_vector_to_blender(value):
    return gltf_to_blender_matrix() @ mathutils.Vector(value)


def gltf_rotation_to_blender(value):
    rotation_matrix = gltf_to_blender_matrix().to_3x3() @ three_euler_xyz_matrix(value)
    return rotation_matrix.to_euler("XYZ")


def three_euler_xyz_matrix(value):
    x, y, z = float(value[0]), float(value[1]), float(value[2])
    a, b = math.cos(x), math.sin(x)
    c, d = math.cos(y), math.sin(y)
    e, f = math.cos(z), math.sin(z)
    return mathutils.Matrix(
        (
            (c * e, -c * f, d),
            (a * f + b * d * e, a * e - b * d * f, -b * c),
            (b * f - a * d * e, b * e + a * d * f, a * c),
        )
    )


def raycast_target(target, origin_world, direction_world, limit):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    world_to_target = evaluated.matrix_world.inverted()
    origin_local = world_to_target @ origin_world
    direction_local = world_to_target.to_3x3() @ direction_world
    if direction_local.length == 0:
        return None
    direction_local.normalize()

    hit, point_local, normal_local, _face_index = evaluated.ray_cast(
        origin_local,
        direction_local,
        distance=float(limit),
    )
    if not hit:
        return None

    point_world = evaluated.matrix_world @ point_local
    normal_world = evaluated.matrix_world.to_3x3().inverted().transposed() @ normal_local
    if normal_world.length == 0:
        normal_world = direction_world.copy()
        normal_world.negate()
    normal_world.normalize()
    return point_world, normal_world


def build_target_projectors(targets):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    projectors = []
    for target in targets:
        try:
            bvh = BVHTree.FromObject(target, depsgraph, deform=True, epsilon=0.0)
        except Exception:
            continue
        if not bvh:
            continue
        matrix_world = target.matrix_world.copy()
        projectors.append(
            {
                "target": target,
                "bvh": bvh,
                "matrix_world": matrix_world,
                "world_to_target": matrix_world.inverted(),
            }
        )
    if not projectors:
        raise RuntimeError("Could not build target surface index for decal projection.")
    return projectors


def closest_nearest_projection(projectors, world_point, depth):
    candidates = []
    for projector in projectors:
        point_local, normal_local, _face_index, _distance = projector["bvh"].find_nearest(
            projector["world_to_target"] @ world_point,
            float(depth),
        )
        if point_local is None or normal_local is None:
            continue

        matrix_world = projector["matrix_world"]
        point_world = matrix_world @ point_local
        world_distance_sq = (point_world - world_point).length_squared
        if world_distance_sq > depth * depth:
            continue

        normal_world = matrix_world.to_3x3().inverted().transposed() @ normal_local
        if normal_world.length == 0:
            normal_world = world_point - point_world
        if normal_world.length == 0:
            normal_world = mathutils.Vector((0, 0, 1))
        normal_world.normalize()
        candidates.append((point_world, normal_world, world_distance_sq))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[2])


def directional_projection(target, world_point, outward_normal, depth):
    origin = world_point + outward_normal * depth
    hit = raycast_target(target, origin, -outward_normal, depth * 2)
    if not hit:
        return None
    point, surface_normal = hit
    return point, surface_normal, (point - world_point).length_squared


def directional_projection_on_targets(targets, world_point, outward_normal, depth):
    candidates = []
    for target in targets:
        projection = directional_projection(target, world_point, outward_normal, depth)
        if projection:
            candidates.append(projection)
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[2])


def decal_outward_normal(decal, obj):
    raw = decal.get("normal")
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        try:
            normal = gltf_vector_to_blender((float(raw[0]), float(raw[1]), float(raw[2])))
            if normal.length > 0:
                normal.normalize()
                return normal
        except Exception:
            pass

    normal = obj.matrix_world.to_quaternion() @ mathutils.Vector((0, 0, 1))
    if normal.length == 0:
        normal = mathutils.Vector((0, 0, 1))
    normal.normalize()
    return normal


def orient_surface_normal(surface_normal, outward_normal):
    normal = surface_normal.copy()
    if normal.length == 0:
        normal = outward_normal.copy()
    if normal.dot(outward_normal) < 0:
        normal.negate()
    normal.normalize()
    return normal


def effective_projection_depth(decal, decal_size):
    configured_depth = max(float(decal["projectionDepth"]), 0.01)
    minimum_depth = max(decal_size * 0.25, 0.01)
    maximum_depth = max(decal_size * 1.25, 0.05)
    return min(10.0, max(minimum_depth, min(configured_depth, maximum_depth)))


def effective_surface_offset(decal, decal_size):
    configured_offset = max(float(decal["offset"]), 0.0)
    return min(0.1, max(configured_offset, decal_size * 0.005, 0.002))


def project_decal_vertices_to_targets(obj, targets, decal):
    if not obj.data.vertices:
        raise RuntimeError(f"Decal {decal['id']} has no vertices to project.")

    bpy.context.view_layer.update()
    world_to_decal = obj.matrix_world.inverted()
    projectors = build_target_projectors(targets)
    outward_normal = decal_outward_normal(decal, obj)

    decal_size = max(float(decal.get("width", 0.0)), float(decal.get("height", 0.0)))
    depth = effective_projection_depth(decal, decal_size)
    offset = effective_surface_offset(decal, decal_size)
    hit_count = 0
    total = len(obj.data.vertices)

    for vertex in obj.data.vertices:
        world_point = obj.matrix_world @ vertex.co
        projection = directional_projection_on_targets(targets, world_point, outward_normal, depth)
        if not projection:
            projection = closest_nearest_projection(projectors, world_point, depth)
        if not projection:
            continue
        point_world, surface_normal, _distance = projection
        surface_normal = orient_surface_normal(surface_normal, outward_normal)
        vertex.co = world_to_decal @ (point_world + surface_normal * offset)
        hit_count += 1

    hit_ratio = hit_count / total
    if hit_count == 0 or hit_ratio < 0.25:
        raise RuntimeError(
            f"Decal {decal['id']} missed the shoe surface "
            f"({hit_count}/{total} projected). Move it closer to the shoe and save again."
        )
    obj.data.update()
    return hit_ratio


def create_decal(decal):
    targets = find_target_meshes(decal.get("targetMeshName", ""))
    if decal.get("kind") == "text":
        obj = create_text_object(decal)
        subdivide_mesh(obj, decal["subdivisions"])
    elif decal["mimeType"] == "image/svg+xml":
        obj = import_svg_object(decal)
        subdivide_mesh(obj, decal["subdivisions"])
    else:
        obj = create_grid_object(decal)
    set_decal_transform(obj, decal)
    project_decal_vertices_to_targets(obj, targets, decal)


try:
    argv = sys.argv[sys.argv.index("--") + 1:]
    source_glb = pathlib.Path(argv[0])
    output_dir = pathlib.Path(argv[1])
    manifest_path = pathlib.Path(argv[2])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    clear_scene()
    import_model(source_glb)
    apply_design_material(manifest.get("material", {}))
    for decal in manifest.get("decals", manifest.get("stickers", [])):
        create_decal(decal)

    bpy.ops.export_scene.gltf(
        filepath=str(output_dir / "final_shoe.glb"),
        export_format="GLB",
    )
    export_obj(output_dir / "final_shoe.obj")
except Exception:
    traceback.print_exc()
    sys.exit(1)
'''.lstrip(),
            encoding="utf-8",
        )
