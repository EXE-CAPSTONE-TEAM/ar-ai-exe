from pathlib import Path

import pytest
from fastapi import HTTPException, status

from app.services.decal_baker import DecalBakeService, MAX_STICKERS


def decal_service() -> DecalBakeService:
    return object.__new__(DecalBakeService)


def test_bake_skips_when_design_has_no_stickers(tmp_path: Path) -> None:
    service = decal_service()

    assert service.bake(tmp_path / "missing.glb", tmp_path, {"stickers": []}) is False


def test_prepare_stickers_decodes_svg_data_uri_and_normalizes_legacy_fields(tmp_path: Path) -> None:
    service = decal_service()
    config = {
        "stickers": [
            {
                "id": "sticker 001",
                "type": "image",
                "imageUrl": "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22/%3E",
                "position": [1, 2, 3],
                "rotation": [0, 1.57, 0],
                "normal": [10, 0, 0],
                "scale": 0.35,
            }
        ]
    }

    stickers = service._prepare_stickers(tmp_path, config)

    assert len(stickers) == 1
    assert stickers[0]["id"] == "sticker_001"
    assert stickers[0]["mimeType"] == "image/svg+xml"
    assert stickers[0]["width"] == pytest.approx(0.35)
    assert stickers[0]["height"] == pytest.approx(0.35)
    assert stickers[0]["normal"] == pytest.approx([1.0, 0.0, 0.0])
    assert stickers[0]["projectionDepth"] == pytest.approx(0.525)
    assert Path(stickers[0]["imagePath"]).read_text(encoding="utf-8").startswith("<svg")


def test_prepare_stickers_rejects_remote_images(tmp_path: Path) -> None:
    service = decal_service()

    with pytest.raises(HTTPException) as exc:
        service._prepare_stickers(
            tmp_path,
            {
                "stickers": [
                    {
                        "id": "remote",
                        "type": "image",
                        "imageUrl": "https://example.com/sticker.png",
                        "position": [0, 0, 0],
                        "rotation": [0, 0, 0],
                        "scale": 0.2,
                    }
                ]
            },
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_prepare_stickers_resolves_uploaded_asset_id(tmp_path: Path) -> None:
    service = decal_service()
    service.asset_resolver = lambda asset_id: (b"\x89PNG\r\n\x1a\nasset-data", "image/png")
    config = {
        "stickers": [
            {
                "id": "uploaded",
                "type": "image",
                "source": "upload",
                "assetId": "asset_001",
                "position": [0, 0, 0],
                "rotation": [0, 0, 0],
                "scale": 0.2,
            }
        ]
    }

    stickers = service._prepare_stickers(tmp_path, config)

    assert len(stickers) == 1
    assert stickers[0]["mimeType"] == "image/png"
    assert stickers[0]["imagePath"].endswith(".png")
    assert Path(stickers[0]["imagePath"]).read_bytes().startswith(b"\x89PNG")


def test_prepare_stickers_rejects_asset_id_without_resolver(tmp_path: Path) -> None:
    service = decal_service()

    with pytest.raises(HTTPException) as exc:
        service._prepare_stickers(
            tmp_path,
            {
                "stickers": [
                    {
                        "id": "uploaded",
                        "type": "image",
                        "assetId": "asset_001",
                        "position": [0, 0, 0],
                        "rotation": [0, 0, 0],
                        "scale": 0.2,
                    }
                ]
            },
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_prepare_decals_includes_text_svg_and_preserves_transform(tmp_path: Path) -> None:
    service = decal_service()
    config = {
        "texts": [
            {
                "id": "text 001",
                "value": "A&B",
                "font": "Arial",
                "color": "#123abc",
                "position": [1, 2, 3],
                "rotation": [0.1, 0.2, 0.3],
                "normal": [0, 0, -2],
                "scale": 0.4,
            }
        ]
    }

    decals = service._prepare_decals(tmp_path, config)

    assert len(decals) == 1
    assert decals[0]["id"] == "text_001"
    assert decals[0]["kind"] == "text"
    assert decals[0]["text"] == "A&B"
    assert decals[0]["position"] == [1.0, 2.0, 3.0]
    assert decals[0]["rotation"] == [0.1, 0.2, 0.3]
    assert decals[0]["normal"] == pytest.approx([0.0, 0.0, -1.0])
    assert decals[0]["width"] >= decals[0]["height"]
    svg = Path(decals[0]["imagePath"]).read_text(encoding="utf-8")
    assert "A&amp;B" in svg
    assert "#123abc" in svg


def test_prepare_decals_uses_render_asset_for_text_layer(tmp_path: Path) -> None:
    service = decal_service()
    service.asset_resolver = lambda asset_id: (b"\xff\xd8\xffjpeg-data", "image/jpeg")
    config = {
        "texts": [
            {
                "id": "text 001",
                "value": "Canvas Font",
                "font": "Impact",
                "color": "#123abc",
                "renderAssetId": "asset_text",
                "position": [1, 2, 3],
                "rotation": [0.1, 0.2, 0.3],
                "scale": 0.4,
            }
        ]
    }

    decals = service._prepare_decals(tmp_path, config)

    assert len(decals) == 1
    assert decals[0]["id"] == "text_001"
    assert decals[0]["kind"] == "image"
    assert decals[0]["mimeType"] == "image/jpeg"
    assert "text" not in decals[0]
    assert Path(decals[0]["imagePath"]).read_bytes().startswith(b"\xff\xd8\xff")


def test_prepare_decals_limits_combined_sticker_and_text_count(tmp_path: Path) -> None:
    service = decal_service()
    config = {
        "stickers": [
            {
                "id": "sticker_001",
                "type": "image",
                "imageUrl": "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22/%3E",
                "position": [0, 0, 0],
                "rotation": [0, 0, 0],
                "scale": 0.2,
            }
        ],
        "texts": [
            {
                "id": f"text_{index}",
                "value": "TAK",
                "position": [0, 0, 0],
                "rotation": [0, 0, 0],
                "scale": 0.2,
            }
            for index in range(MAX_STICKERS)
        ],
    }

    with pytest.raises(HTTPException) as exc:
        service._prepare_decals(tmp_path, config)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_prepare_material_sanitizes_base_color_and_material_values() -> None:
    service = decal_service()

    material = service._prepare_material(
        {
            "baseColor": "not-a-color",
            "material": {
                "roughness": 2,
                "metallic": -1,
            },
        }
    )

    assert material == {
        "baseColor": "#ffffff",
        "roughness": 1.0,
        "metallic": 0.0,
    }


def test_prepare_material_preserves_valid_base_color_and_material_values() -> None:
    service = decal_service()

    material = service._prepare_material(
        {
            "baseColor": "#123abc",
            "material": {
                "roughness": 0.8,
                "metallic": 0.2,
            },
        }
    )

    assert material == {
        "baseColor": "#123abc",
        "roughness": 0.8,
        "metallic": 0.2,
    }


def test_blender_script_uses_explicit_projection_and_miss_guard(tmp_path: Path) -> None:
    service = decal_service()
    script_path = tmp_path / "apply_decals.py"

    service._write_blender_script(script_path)
    script = script_path.read_text(encoding="utf-8")

    compile(script, str(script_path), "exec")
    assert "import math" in script
    assert "def project_decal_vertices_to_targets" in script
    assert "def find_target_meshes" in script
    assert "from mathutils.bvhtree import BVHTree" in script
    assert "def build_target_projectors" in script
    assert "def directional_projection" in script
    assert "def decal_outward_normal" in script
    assert "def gltf_vector_to_blender" in script
    assert "def gltf_rotation_to_blender" in script
    assert "def three_euler_xyz_matrix" in script
    assert "three_euler_xyz_matrix(value)" in script
    assert "def apply_design_material" in script
    assert "def apply_material_settings" in script
    assert "not base_color.links" in script
    assert "target.data.materials.clear()" not in script
    assert "polygon.material_index = 0" in script
    assert "apply_design_material(manifest.get(\"material\", {}))" in script
    assert script.index("apply_design_material(manifest.get(\"material\", {}))") < script.index(
        "for decal in manifest.get"
    )
    assert 'Matrix.Rotation(1.5707963267948966, 4, "X")' in script
    assert "def orient_surface_normal" in script
    assert "def orient_surface_normal(surface_normal, outward_normal)" in script
    assert "def effective_projection_depth" in script
    assert "def effective_surface_offset" in script
    assert "find_nearest" in script
    assert "return candidates" in script
    assert "def apply_shrinkwrap" not in script
    assert "distance=float(limit)" in script
    assert "decal_size * 2.0" not in script
    assert "decal_size * 1.25" in script
    assert "projection = directional_projection_on_targets" in script
    assert "projection = closest_nearest_projection" in script
    assert "reference_direction = world_point - point_world" not in script
    assert "surface_normal = orient_surface_normal(surface_normal, outward_normal)" in script
    assert "material.use_backface_culling = False" in script
    assert "missed the shoe surface" in script
    assert "hit_ratio < 0.25" in script


def test_blender_script_assigns_text_material_after_mesh_conversion(tmp_path: Path) -> None:
    service = decal_service()
    script_path = tmp_path / "apply_decals.py"

    service._write_blender_script(script_path)
    script = script_path.read_text(encoding="utf-8")
    convert_index = script.index('bpy.ops.object.convert(target="MESH")', script.index("def create_text_object"))
    material_index = script.index("converted.data.materials.append(create_solid_material(decal))")

    assert convert_index < material_index
