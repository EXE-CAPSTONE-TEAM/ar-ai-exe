"""Auto-sculpt & bake pipeline service.

Orchestrates Blender in headless mode to remesh, smooth, decimate, and bake
normal + diffuse maps from a high-poly scan mesh to a lightweight low-poly
version suitable for mobile clients.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.blender_service import BlenderService
from app.services.command_runner import CommandRunner


@dataclass(frozen=True)
class SculptResult:
    """Paths and metrics produced by the auto-sculpt & bake pipeline."""

    low_poly_obj: Path
    low_poly_glb: Path
    normal_map: Path
    diffuse_texture: Path
    high_poly_face_count: int
    low_poly_face_count: int
    reduction_ratio: float


class MeshSculptService:
    """Run Blender auto-sculpt: remesh → smooth → decimate → bake normal + diffuse."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.blender = BlenderService()
        self.runner = CommandRunner()

    def sculpt_and_bake(
        self,
        input_mesh: Path,
        output_dir: Path,
        log_path: Path,
        timeout: int | None = None,
    ) -> SculptResult:
        """Execute the full sculpt & bake pipeline, returning paths to output assets.

        Args:
            input_mesh: Path to the raw high-poly OBJ from OpenMVS.
            output_dir: Directory to write sculpted assets into.
            log_path: File to append pipeline stdout/stderr logs.
            timeout: Command timeout in seconds (defaults to reconstruction setting).

        Returns:
            SculptResult with paths to low-poly OBJ, GLB, normal map, and diffuse texture.

        Raises:
            RuntimeError: If the Blender script fails or expected outputs are missing.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / "auto_sculpt_bake.py"
        self._write_sculpt_script(script_path)

        command = self.blender.sculpt_bake_command(
            script_path=script_path,
            input_mesh_path=input_mesh,
            output_dir=output_dir,
            voxel_size=self.settings.sculpt_voxel_size,
            smooth_iterations=self.settings.sculpt_smooth_iterations,
            smooth_factor=self.settings.sculpt_smooth_factor,
            decimate_ratio=self.settings.sculpt_decimate_ratio,
            normal_map_size=self.settings.sculpt_normal_map_size,
            texture_size=self.settings.sculpt_texture_size,
        )

        effective_timeout = timeout or self.settings.reconstruction_command_timeout_seconds
        result = self.runner.run(
            command,
            log_path=log_path,
            cwd=output_dir,
            timeout=effective_timeout,
        )
        if not result.ok:
            message = result.stderr.strip() or result.stdout.strip() or "Blender sculpt failed."
            raise RuntimeError(f"Auto-sculpt & bake failed: {message[-1200:]}")

        return self._validate_outputs(output_dir, result.stdout)

    def _validate_outputs(self, output_dir: Path, stdout: str) -> SculptResult:
        """Verify all expected files exist and parse face-count metrics from stdout."""
        expected = {
            "low_poly.obj": output_dir / "low_poly.obj",
            "low_poly.glb": output_dir / "low_poly.glb",
            "normal_map.png": output_dir / "normal_map.png",
            "diffuse_texture.png": output_dir / "diffuse_texture.png",
        }
        for name, path in expected.items():
            if not path.is_file():
                raise RuntimeError(f"Auto-sculpt did not produce {name}.")

        high_poly_count = self._parse_metric(stdout, "HIGH_POLY_FACES")
        low_poly_count = self._parse_metric(stdout, "LOW_POLY_FACES")
        reduction = low_poly_count / max(high_poly_count, 1)

        return SculptResult(
            low_poly_obj=expected["low_poly.obj"],
            low_poly_glb=expected["low_poly.glb"],
            normal_map=expected["normal_map.png"],
            diffuse_texture=expected["diffuse_texture.png"],
            high_poly_face_count=high_poly_count,
            low_poly_face_count=low_poly_count,
            reduction_ratio=round(reduction, 4),
        )

    def _parse_metric(self, stdout: str, key: str) -> int:
        """Extract an integer metric printed by the Blender script as `KEY=value`."""
        for line in stdout.splitlines():
            if line.startswith(f"{key}="):
                try:
                    return int(line.split("=", 1)[1].strip())
                except (ValueError, IndexError):
                    pass
        return 0

    def _write_sculpt_script(self, script_path: Path) -> None:
        """Write the Blender Python script that performs remesh, smooth, decimate, and bake."""
        script_path.write_text(
            _BLENDER_SCULPT_SCRIPT,
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Blender Python script (runs inside `blender --background --python`)
#
# Accepts CLI args after `--`:
#   <input_mesh.obj> <output_dir>
#   --voxel-size 0.005 --smooth-iterations 5 --smooth-factor 0.5
#   --decimate-ratio 0.08 --normal-map-size 2048 --texture-size 2048
#
# Outputs:
#   output_dir/low_poly.obj
#   output_dir/low_poly.glb
#   output_dir/normal_map.png
#   output_dir/diffuse_texture.png
#
# Prints metrics to stdout:
#   HIGH_POLY_FACES=<int>
#   LOW_POLY_FACES=<int>
# ---------------------------------------------------------------------------
_BLENDER_SCULPT_SCRIPT = r'''
import argparse
import pathlib
import sys
import traceback

import bpy


def parse_args():
    """Parse CLI arguments passed after the Blender `--` separator."""
    argv = sys.argv[sys.argv.index("--") + 1:]
    parser = argparse.ArgumentParser(description="Auto-sculpt & bake pipeline")
    parser.add_argument("input_mesh", type=pathlib.Path)
    parser.add_argument("output_dir", type=pathlib.Path)
    parser.add_argument("--voxel-size", type=float, default=0.005)
    parser.add_argument("--smooth-iterations", type=int, default=5)
    parser.add_argument("--smooth-factor", type=float, default=0.5)
    parser.add_argument("--decimate-ratio", type=float, default=0.08)
    parser.add_argument("--normal-map-size", type=int, default=2048)
    parser.add_argument("--texture-size", type=int, default=2048)
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_obj(path):
    """Import OBJ using the available Blender API (4.x or legacy)."""
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        bpy.ops.import_scene.obj(filepath=str(path))


def get_mesh_objects():
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def join_meshes(objects):
    """Join multiple mesh objects into a single object."""
    if len(objects) <= 1:
        return objects[0] if objects else None
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def apply_voxel_remesh(obj, voxel_size):
    """Apply voxel remesh to redistribute faces uniformly."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new(name="Remesh", type="REMESH")
    modifier.mode = "VOXEL"
    modifier.voxel_size = voxel_size
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def apply_smooth(obj, iterations, factor):
    """Apply corrective smooth modifier to reduce scan noise."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new(name="Smooth", type="CORRECTIVE_SMOOTH")
    modifier.iterations = iterations
    modifier.scale = factor
    modifier.use_pin_boundary = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def face_count(obj):
    return len(obj.data.polygons)


def duplicate_object(obj, name):
    """Create a deep copy of a mesh object."""
    new_mesh = obj.data.copy()
    new_obj = obj.copy()
    new_obj.data = new_mesh
    new_obj.name = name
    bpy.context.scene.collection.objects.link(new_obj)
    return new_obj


def decimate_mesh(obj, ratio):
    """Apply decimate modifier to reduce polygon count."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new(name="Decimate", type="DECIMATE")
    modifier.ratio = max(0.01, min(1.0, ratio))
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def smart_uv_project(obj):
    """Generate UV layout on the low-poly mesh for baking."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def create_bake_image(name, size):
    """Create an image for baking output."""
    image = bpy.data.images.new(name, width=size, height=size, alpha=True)
    image.colorspace_settings.name = "Non-Color" if "normal" in name.lower() else "sRGB"
    return image


def prepare_bake_material(obj, image):
    """Assign a material with an image texture node selected for baking output."""
    if not obj.data.materials:
        material = bpy.data.materials.new(name="BakeMaterial")
        material.use_nodes = True
        obj.data.materials.append(material)

    material = obj.data.materials[0]
    if not material.use_nodes:
        material.use_nodes = True
    nodes = material.node_tree.nodes
    texture_node = nodes.new("ShaderNodeTexImage")
    texture_node.image = image
    texture_node.name = "BakeTarget"
    # Selecting the node tells Blender to bake into this image
    nodes.active = texture_node
    return material


def bake_normal_map(high_poly, low_poly, image_size):
    """Bake normals from high-poly to low-poly via selected-to-active."""
    image = create_bake_image("NormalMap", image_size)
    image.colorspace_settings.name = "Non-Color"
    prepare_bake_material(low_poly, image)

    # Ensure Cycles renderer for baking
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.device = "CPU"
    bpy.context.scene.cycles.samples = 1
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False
    bpy.context.scene.render.bake.use_selected_to_active = True
    bpy.context.scene.render.bake.cage_extrusion = 0.1
    bpy.context.scene.render.bake.max_ray_distance = 0.2

    # Select high-poly, set low-poly as active
    bpy.ops.object.select_all(action="DESELECT")
    high_poly.select_set(True)
    low_poly.select_set(True)
    bpy.context.view_layer.objects.active = low_poly

    bpy.ops.object.bake(type="NORMAL")
    return image


def bake_diffuse_texture(high_poly, low_poly, image_size):
    """Bake diffuse color from high-poly to low-poly via selected-to-active."""
    image = create_bake_image("DiffuseTexture", image_size)
    prepare_bake_material(low_poly, image)

    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.device = "CPU"
    bpy.context.scene.cycles.samples = 1
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False
    bpy.context.scene.render.bake.use_pass_color = True
    bpy.context.scene.render.bake.use_selected_to_active = True
    bpy.context.scene.render.bake.cage_extrusion = 0.1
    bpy.context.scene.render.bake.max_ray_distance = 0.2

    bpy.ops.object.select_all(action="DESELECT")
    high_poly.select_set(True)
    low_poly.select_set(True)
    bpy.context.view_layer.objects.active = low_poly

    bpy.ops.object.bake(type="DIFFUSE")
    return image


def save_image(image, path):
    """Save a Blender image to disk as PNG."""
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save_render(str(path))


def setup_low_poly_material(low_poly, diffuse_image, normal_image):
    """Wire diffuse + normal map into the low-poly material for GLB export."""
    if not low_poly.data.materials:
        material = bpy.data.materials.new(name="SculptedMaterial")
        low_poly.data.materials.append(material)

    material = low_poly.data.materials[0]
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear existing nodes except output
    output_node = None
    for node in nodes:
        if node.type == "OUTPUT_MATERIAL":
            output_node = node
        else:
            nodes.remove(node)

    if not output_node:
        output_node = nodes.new("ShaderNodeOutputMaterial")
        output_node.location = (400, 0)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

    # Diffuse texture
    diffuse_tex = nodes.new("ShaderNodeTexImage")
    diffuse_tex.image = diffuse_image
    diffuse_tex.location = (-400, 200)
    links.new(diffuse_tex.outputs["Color"], bsdf.inputs["Base Color"])

    # Normal map
    normal_tex = nodes.new("ShaderNodeTexImage")
    normal_tex.image = normal_image
    normal_tex.image.colorspace_settings.name = "Non-Color"
    normal_tex.location = (-400, -200)

    normal_map_node = nodes.new("ShaderNodeNormalMap")
    normal_map_node.location = (-100, -200)
    links.new(normal_tex.outputs["Color"], normal_map_node.inputs["Color"])
    links.new(normal_map_node.outputs["Normal"], bsdf.inputs["Normal"])


def export_obj(obj, path):
    """Export a single object as OBJ."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if hasattr(bpy.ops.wm, "obj_export"):
        try:
            bpy.ops.wm.obj_export(
                filepath=str(path),
                export_selected_objects=True,
                export_materials=True,
                path_mode="COPY",
            )
        except TypeError:
            bpy.ops.wm.obj_export(
                filepath=str(path),
                export_selected_objects=True,
                export_materials=True,
            )
    else:
        bpy.ops.export_scene.obj(
            filepath=str(path),
            use_selection=True,
            use_materials=True,
            path_mode="COPY",
        )


def export_glb(obj, path):
    """Export a single object as GLB."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
    )


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    import_obj(args.input_mesh)

    meshes = get_mesh_objects()
    if not meshes:
        raise RuntimeError("No mesh objects found in imported file.")

    high_poly = join_meshes(meshes)
    high_poly.name = "HighPoly"
    high_poly_faces = face_count(high_poly)
    print(f"HIGH_POLY_FACES={high_poly_faces}", flush=True)

    # Step 1: Voxel remesh for uniform face distribution
    apply_voxel_remesh(high_poly, args.voxel_size)

    # Step 2: Smooth to reduce scan noise
    apply_smooth(high_poly, args.smooth_iterations, args.smooth_factor)

    # Step 3: Create low-poly copy via decimation
    low_poly = duplicate_object(high_poly, "LowPoly")
    decimate_mesh(low_poly, args.decimate_ratio)
    low_poly_faces = face_count(low_poly)
    print(f"LOW_POLY_FACES={low_poly_faces}", flush=True)

    # Step 4: UV unwrap the low-poly mesh for bake targets
    smart_uv_project(low_poly)

    # Step 5: Bake normal map (high → low)
    normal_image = bake_normal_map(high_poly, low_poly, args.normal_map_size)
    normal_path = args.output_dir / "normal_map.png"
    save_image(normal_image, normal_path)

    # Step 6: Bake diffuse texture (high → low)
    diffuse_image = bake_diffuse_texture(high_poly, low_poly, args.texture_size)
    diffuse_path = args.output_dir / "diffuse_texture.png"
    save_image(diffuse_image, diffuse_path)

    # Step 7: Set up material on low-poly with baked textures
    setup_low_poly_material(low_poly, diffuse_image, normal_image)

    # Step 8: Remove high-poly from scene, export low-poly
    bpy.data.objects.remove(high_poly, do_unlink=True)

    export_obj(low_poly, args.output_dir / "low_poly.obj")
    export_glb(low_poly, args.output_dir / "low_poly.glb")

    print("SCULPT_BAKE_COMPLETE", flush=True)


try:
    main()
except Exception:
    traceback.print_exc()
    sys.exit(1)
'''.lstrip()
