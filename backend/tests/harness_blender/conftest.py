"""Pytest fixtures for headless Blender 3D integration suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from harness.doctor import find_blender_binary
from harness.fixtures.procedural_mesh import generate_curved_test_mesh


@pytest.fixture(scope="session")
def blender_executable() -> Path:
    """Ensure Blender executable is located and registered in environment."""
    binary = find_blender_binary()
    if not binary:
        pytest.skip("Headless Blender tests skipped: Blender binary was not found.")

    os.environ["BLENDER_BIN"] = str(binary)
    get_settings.cache_clear()
    return binary


@pytest.fixture
def curved_mesh_glb(tmp_path: Path, blender_executable: Path) -> Path:
    """Generate a clean procedural curved test GLB in temporary directory."""
    mesh_path = tmp_path / "procedural_curved.glb"
    return generate_curved_test_mesh(mesh_path, blender_executable)


@pytest.fixture
def demo_shoe_glb(blender_executable: Path) -> Path:
    """Return path to repository standard 3DModel.glb."""
    repo_root = Path(__file__).resolve().parents[3]
    demo_path = repo_root / "data" / "3DModel.glb"
    if not demo_path.is_file():
        pytest.skip("Standard model data/3DModel.glb not found.")
    return demo_path
