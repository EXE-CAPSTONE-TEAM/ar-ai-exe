"""Real headless Blender mesh cleanup integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.mesh_cleanup import MeshCleanupOptions, MeshCleanupService
from tests.harness_blender.test_real_decal_bake import assert_valid_glb


def test_real_mesh_cleanup_curved_mesh(curved_mesh_glb: Path, tmp_path: Path) -> None:
    """Test executing actual Blender background process normalizing mesh origin, bounds, and scale."""
    service = MeshCleanupService()
    output_dir = tmp_path / "cleanup_curved_out"

    report = service.cleanup(
        source_model=curved_mesh_glb,
        output_dir=output_dir,
    )

    assert report.editor_ready is True
    assert report.editor_ready_score > 0
    assert report.mesh_object_count >= 1

    # Canonical editor assets must exist
    assert_valid_glb(output_dir / "shoe_preview.glb")
    assert (output_dir / "shoe.obj").is_file()
    assert (output_dir / "shoe.mtl").is_file()
    assert (output_dir / "_mesh_cleanup" / "mesh_cleanup_report.json").is_file()


def test_real_mesh_cleanup_demo_shoe(demo_shoe_glb: Path, tmp_path: Path) -> None:
    """Test executing real cleanup on the repository 3DModel.glb."""
    service = MeshCleanupService()
    output_dir = tmp_path / "cleanup_real_shoe_out"

    report = service.cleanup(
        source_model=demo_shoe_glb,
        output_dir=output_dir,
    )

    assert report.editor_ready is True
    assert report.mesh_object_count >= 1
    assert_valid_glb(output_dir / "shoe_preview.glb")
    assert (output_dir / "shoe.obj").is_file()
