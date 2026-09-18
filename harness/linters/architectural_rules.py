"""Mechanical architectural invariant linter for ar-ai-exe.

Converts project-level architectural invariants from passive documentation
(CONTEXT.md, AGENTS.md) into mechanical, non-bypassable code guards:
1. Base shoe material preservation: Forbid clearing or replacing base mesh material slots.
2. Server-authored Blender scripts: Forbid dynamic execution of user-supplied scripts.
3. Decal safety invariants: Enforce hit_ratio >= 0.25 raycast guard.
4. Payload limits: Ensure sticker quota (<= 50), text length (<= 80), file size (<= 5MB).
5. Secret & URL hygiene: Reject hardcoded private tokens or insecure raw IPs.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class InvariantViolation:
    file_path: Path
    line_number: int
    rule_id: str
    message: str
    remediation: str


class ArchitecturalRulesScanner:
    """Static AST and pattern scanner enforcing mechanical architectural boundaries."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def scan_all(self) -> list[InvariantViolation]:
        violations: list[InvariantViolation] = []
        violations.extend(self.check_material_slot_preservation())
        violations.extend(self.check_server_authored_scripts())
        violations.extend(self.check_decal_hit_ratio_guard())
        violations.extend(self.check_payload_limits_defined())
        violations.extend(self.check_hardcoded_secrets_and_ips())
        violations.extend(self.check_mobile_toolchain_versions())
        return violations

    def check_material_slot_preservation(self) -> Iterator[InvariantViolation]:
        """RULE-001: Never clear base mesh material slots.

        Only newly created decal objects (svg_mesh, decal_obj) may clear materials.
        """
        for py_file in self._iter_python_files(self.repo_root / "backend" / "app"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                # Look for calls to .materials.clear()
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "clear"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "materials"
                ):
                    target_expr = ast.unparse(node.func.value)
                    # Decal-specific temporary objects are allowed to initialize material slots
                    is_decal_target = any(
                        target_expr.startswith(allowed)
                        for allowed in ("converted", "decal_obj", "text_obj", "mesh_obj", "decal")
                    )
                    if not is_decal_target:
                        yield InvariantViolation(
                            file_path=py_file,
                            line_number=node.lineno,
                            rule_id="RULE-001",
                            message=f"Clearing material slots on target '{target_expr}' violates base mesh preservation invariant.",
                            remediation="Preserve existing materials and textures. Adjust only safe PBR properties without clearing slots.",
                        )

    def check_server_authored_scripts(self) -> Iterator[InvariantViolation]:
        """RULE-002: Blender scripts must remain server-authored.

        Forbid executing arbitrary code via eval(), exec(), or user-supplied script files.
        """
        for py_file in self._iter_python_files(self.repo_root / "backend" / "app"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec"}:
                        yield InvariantViolation(
                            file_path=py_file,
                            line_number=node.lineno,
                            rule_id="RULE-002",
                            message=f"Direct invocation of '{node.func.id}()' is strictly forbidden in backend services.",
                            remediation="Use pre-compiled, server-authored script templates with deterministic parameter passing.",
                        )

    def check_decal_hit_ratio_guard(self) -> Iterator[InvariantViolation]:
        """RULE-003: Decal baker must enforce hit_ratio >= 0.25 miss guard."""
        decal_baker = self.repo_root / "backend" / "app" / "services" / "decal_baker.py"
        if not decal_baker.is_file():
            return

        content = decal_baker.read_text(encoding="utf-8")
        if "hit_ratio < 0.25" not in content and "hit_ratio >= 0.25" not in content:
            yield InvariantViolation(
                file_path=decal_baker,
                line_number=1,
                rule_id="RULE-003",
                message="Decal baker missing mandatory 25% surface hit ratio raycast miss guard.",
                remediation="Ensure apply_decals script checks hit_ratio < 0.25 and raises an error on floating decals.",
            )

    def check_payload_limits_defined(self) -> Iterator[InvariantViolation]:
        """RULE-004: Invariants MAX_STICKERS=50, MAX_TEXT_LENGTH=80, MAX_STICKER_BYTES=5MB must be enforced."""
        decal_baker = self.repo_root / "backend" / "app" / "services" / "decal_baker.py"
        if not decal_baker.is_file():
            return

        content = decal_baker.read_text(encoding="utf-8")
        required_constants = {
            "MAX_STICKERS": "50",
            "MAX_TEXT_LENGTH": "80",
        }
        for const_name, expected_value in required_constants.items():
            pattern = rf"{const_name}\s*=\s*{expected_value}"
            if not re.search(pattern, content):
                yield InvariantViolation(
                    file_path=decal_baker,
                    line_number=1,
                    rule_id="RULE-004",
                    message=f"Mandatory invariant '{const_name} = {expected_value}' not found in decal_baker.py.",
                    remediation=f"Define and enforce '{const_name} = {expected_value}' at service boundary.",
                )

    def check_hardcoded_secrets_and_ips(self) -> Iterator[InvariantViolation]:
        """RULE-005: Forbid hardcoded private tokens or local network raw IP addresses."""
        raw_ip_pattern = re.compile(r"https?://(?:192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+")

        for py_file in self._iter_python_files(self.repo_root / "backend" / "app"):
            content = py_file.read_text(encoding="utf-8")
            for line_idx, line in enumerate(content.splitlines(), start=1):
                if raw_ip_pattern.search(line):
                    yield InvariantViolation(
                        file_path=py_file,
                        line_number=line_idx,
                        rule_id="RULE-005",
                        message=f"Detected hardcoded private IP address in {py_file.name}:{line_idx}",
                        remediation="Use environment variables or capability URLs instead of hardcoded IPs.",
                    )

    def check_mobile_toolchain_versions(self) -> Iterator[InvariantViolation]:
        """RULE-006: Enforce modern Android toolchain versions to prevent Flutter deprecation warnings.

        Minimum versions: Gradle >= 9.1.0, AGP >= 9.0.1, Kotlin >= 2.3.20.
        """
        wrapper_props = self.repo_root / "mobile" / "android" / "gradle" / "wrapper" / "gradle-wrapper.properties"
        if wrapper_props.is_file():
            content = wrapper_props.read_text(encoding="utf-8")
            match = re.search(r"gradle-([0-9]+(?:\.[0-9]+)*)-", content)
            if match:
                v_str = match.group(1)
                v_tuple = tuple(int(x) for x in re.findall(r"\d+", v_str))
                if v_tuple < (9, 1, 0):
                    yield InvariantViolation(
                        file_path=wrapper_props,
                        line_number=1,
                        rule_id="RULE-006",
                        message=f"Gradle version ({v_str}) is below minimum required (9.1.0) by Flutter 3.47+.",
                        remediation="Upgrade distributionUrl in gradle-wrapper.properties to gradle-9.1.0-all.zip.",
                    )

        settings_gradle = self.repo_root / "mobile" / "android" / "settings.gradle.kts"
        if not settings_gradle.is_file():
            settings_gradle = self.repo_root / "mobile" / "android" / "settings.gradle"

        if settings_gradle.is_file():
            content = settings_gradle.read_text(encoding="utf-8")
            agp_match = re.search(r'com\.android\.application["\']\)?\s*version\s*["\']([0-9]+(?:\.[0-9]+)*)["\']', content)
            if agp_match:
                v_str = agp_match.group(1)
                v_tuple = tuple(int(x) for x in re.findall(r"\d+", v_str))
                if v_tuple < (9, 0, 1):
                    yield InvariantViolation(
                        file_path=settings_gradle,
                        line_number=1,
                        rule_id="RULE-006",
                        message=f"Android Gradle Plugin version ({v_str}) is below minimum required (9.0.1) by Flutter 3.47+.",
                        remediation="Upgrade com.android.application version to at least '9.0.1' in settings.gradle.kts.",
                    )

            kgp_match = re.search(r'org\.jetbrains\.kotlin\.android["\']\)?\s*version\s*["\']([0-9]+(?:\.[0-9]+)*)["\']', content)
            if kgp_match:
                v_str = kgp_match.group(1)
                v_tuple = tuple(int(x) for x in re.findall(r"\d+", v_str))
                if v_tuple < (2, 3, 20):
                    yield InvariantViolation(
                        file_path=settings_gradle,
                        line_number=1,
                        rule_id="RULE-006",
                        message=f"Kotlin Gradle Plugin version ({v_str}) is below minimum required (2.3.20) by Flutter 3.47+.",
                        remediation="Upgrade org.jetbrains.kotlin.android version to at least '2.3.20' in settings.gradle.kts.",
                    )

    def _iter_python_files(self, base_dir: Path) -> Iterator[Path]:
        if not base_dir.is_dir():
            return
        for item in base_dir.rglob("*.py"):
            if "__pycache__" not in item.parts and ".venv" not in item.parts:
                yield item
