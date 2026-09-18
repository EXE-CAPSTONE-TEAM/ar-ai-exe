"""Real headless Blender decal bake tests validating 3D geometry and invariants."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.decal_baker import DecalBakeService
from harness.fixtures.procedural_mesh import (
    SAMPLE_SVG_DATA_URI,
    build_design_payload,
    sample_sticker_config,
    sample_text_config,
)


def assert_valid_glb(path: Path) -> None:
    """Assert file exists and starts with valid binary glTF 2.0 header."""
    assert path.is_file(), f"Expected GLB file {path} to exist"
    assert path.stat().st_size > 500, f"File {path} is too small"
    with open(path, "rb") as f:
        header = f.read(12)
    magic, version, length = struct.unpack("<4sII", header)
    assert magic == b"glTF", f"Invalid magic header: {magic}"
    assert version == 2, f"Expected glTF version 2, got {version}"
    assert length == path.stat().st_size, f"Header length {length} != file size {path.stat().st_size}"


def test_real_bake_svg_sticker_on_curved_mesh(curved_mesh_glb: Path, tmp_path: Path) -> None:
    """Test executing actual Blender background process projecting an SVG sticker onto curved mesh."""
    service = DecalBakeService()
    output_dir = tmp_path / "bake_svg_out"

    sticker = sample_sticker_config(
        sticker_id="test_sticker_svg",
        image_url=SAMPLE_SVG_DATA_URI,
        position=[0.0, 0.0, 0.2],
        rotation=[0.0, 0.0, 0.0],
        scale=0.2,
    )
    design = build_design_payload(stickers=[sticker])

    success = service.bake(
        source_glb=curved_mesh_glb,
        output_dir=output_dir,
        design_config=design,
    )

    assert success is True
    assert_valid_glb(output_dir / "final_shoe.glb")
    assert (output_dir / "final_shoe.obj").is_file()
    assert (output_dir / "final_shoe.mtl").is_file()


def test_real_bake_text_layer_on_curved_mesh(curved_mesh_glb: Path, tmp_path: Path) -> None:
    """Test executing actual Blender process rendering and converting text into projected 3D geometry."""
    service = DecalBakeService()
    output_dir = tmp_path / "bake_text_out"

    text = sample_text_config(
        text_id="text_layer_01",
        value="KUS",
        position=[0.0, 0.0, 0.2],
        scale=0.2,
    )
    design = build_design_payload(stickers=[], texts=[text])

    success = service.bake(
        source_glb=curved_mesh_glb,
        output_dir=output_dir,
        design_config=design,
    )

    assert success is True
    assert_valid_glb(output_dir / "final_shoe.glb")


def test_real_bake_enforces_hit_ratio_miss_guard(curved_mesh_glb: Path, tmp_path: Path) -> None:
    """Invariant test: A decal floating in space must be caught by raycast miss guard (hit_ratio < 0.25)."""
    service = DecalBakeService()
    output_dir = tmp_path / "bake_floating_out"

    floating_sticker = sample_sticker_config(
        sticker_id="floating_lost",
        image_url=SAMPLE_SVG_DATA_URI,
        position=[50.0, 50.0, 50.0],  # Way outside mesh bounding box [-1, 1]
        rotation=[0.0, 0.0, 0.0],
        scale=0.2,
    )
    design = build_design_payload(stickers=[floating_sticker])

    with pytest.raises(HTTPException) as exc:
        service.bake(
            source_glb=curved_mesh_glb,
            output_dir=output_dir,
            design_config=design,
        )

    assert exc.value.status_code == 400
    assert "missed the shoe surface" in exc.value.detail or "hit_ratio" in exc.value.detail


def test_real_bake_demo_shoe_asset(demo_shoe_glb: Path, tmp_path: Path) -> None:
    """Test baking onto the real repository 3DModel.glb."""
    service = DecalBakeService()
    output_dir = tmp_path / "bake_real_shoe_out"

    # Mesh bounds center & size for 3DModel.glb
    c = [-0.083, 0.18, -0.512]
    s = [1.28, 0.456, 0.557]
    scale = 0.15

    sticker = {
        "id": "real_shoe_sticker",
        "type": "image",
        "imageUrl": SAMPLE_SVG_DATA_URI,
        "position": [c[0] + s[0] * 0.35, c[1], c[2]],
        "rotation": [0.0, 1.57, 0.0],
        "normal": [1.0, 0.0, 0.0],
        "scale": scale,
        "width": scale,
        "height": scale,
        "projectionDepth": 1.5,
        "offset": 0.004,
    }
    design = build_design_payload(stickers=[sticker])

    success = service.bake(
        source_glb=demo_shoe_glb,
        output_dir=output_dir,
        design_config=design,
    )

    assert success is True
    assert_valid_glb(output_dir / "final_shoe.glb")
