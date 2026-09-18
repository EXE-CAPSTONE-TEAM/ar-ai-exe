"""Unit tests for the mechanical architectural rules linter."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.linters.architectural_rules import ArchitecturalRulesScanner


def test_linter_detects_material_slot_clearing(tmp_path: Path) -> None:
    """Linter must catch .materials.clear() when invoked on base mesh objects."""
    bad_code = """
import bpy

def mutate_shoe(shoe_mesh):
    # VIOLATION: Clearing materials on base mesh object
    shoe_mesh.data.materials.clear()
"""
    app_dir = tmp_path / "backend" / "app"
    app_dir.mkdir(parents=True)
    test_file = app_dir / "bad_mutator.py"
    test_file.write_text(bad_code, encoding="utf-8")

    scanner = ArchitecturalRulesScanner(tmp_path)
    violations = list(scanner.check_material_slot_preservation())

    assert len(violations) == 1
    assert violations[0].rule_id == "RULE-001"
    assert "shoe_mesh" in violations[0].message


def test_linter_detects_forbidden_eval(tmp_path: Path) -> None:
    """Linter must catch eval() or exec() usage in backend code."""
    bad_code = """
def run_dynamic(user_input):
    return eval(user_input)
"""
    app_dir = tmp_path / "backend" / "app"
    app_dir.mkdir(parents=True)
    test_file = app_dir / "dynamic.py"
    test_file.write_text(bad_code, encoding="utf-8")

    scanner = ArchitecturalRulesScanner(tmp_path)
    violations = list(scanner.check_server_authored_scripts())

    assert len(violations) == 1
    assert violations[0].rule_id == "RULE-002"
    assert "eval" in violations[0].message


def test_linter_detects_outdated_mobile_toolchain(tmp_path: Path) -> None:
    """Linter must detect outdated Gradle, AGP, or Kotlin versions."""
    gradle_dir = tmp_path / "mobile" / "android" / "gradle" / "wrapper"
    gradle_dir.mkdir(parents=True)
    (gradle_dir / "gradle-wrapper.properties").write_text(
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14-all.zip\n",
        encoding="utf-8",
    )

    settings_file = tmp_path / "mobile" / "android" / "settings.gradle.kts"
    settings_file.write_text(
        'plugins {\n    id("com.android.application") version "8.11.1" apply false\n    id("org.jetbrains.kotlin.android") version "2.2.20" apply false\n}\n',
        encoding="utf-8",
    )

    scanner = ArchitecturalRulesScanner(tmp_path)
    violations = list(scanner.check_mobile_toolchain_versions())

    assert len(violations) == 3
    rule_ids = {v.rule_id for v in violations}
    assert rule_ids == {"RULE-006"}
    messages = " ".join(v.message for v in violations)
    assert "Gradle version (8.14)" in messages
    assert "Android Gradle Plugin version (8.11.1)" in messages
    assert "Kotlin Gradle Plugin version (2.2.20)" in messages


def test_current_repo_passes_all_architectural_rules() -> None:
    """The production repository must have 0 architectural rule violations."""
    scanner = ArchitecturalRulesScanner(REPO_ROOT)
    violations = scanner.scan_all()
    assert violations == [], f"Architectural violations found: {violations}"
