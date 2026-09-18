"""Test Impact Analysis (TIA) Engine for ar-ai-exe.

Analyzes modified files from git diff and maps them to affected test suites
to ensure Pre-submit Gate feedback completes in under 3 minutes.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Set


@dataclass(frozen=True)
class ImpactAnalysisResult:
    changed_files: list[str]
    run_lint: bool
    run_backend_unit: bool
    run_blender_3d: bool
    run_control_plane: bool
    run_frontend: bool

    def summary(self) -> str:
        suites = []
        if self.run_lint:
            suites.append("lint")
        if self.run_backend_unit:
            suites.append("backend_unit")
        if self.run_control_plane:
            suites.append("control_plane")
        if self.run_blender_3d:
            suites.append("blender_3d (heavy)")
        if self.run_frontend:
            suites.append("frontend")
        return ", ".join(suites) if suites else "none (no impacted code detected)"


class TestImpactAnalyzer:
    """Calculates downstream test impacts based on git changes."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def get_changed_files(self) -> list[str]:
        """Detect uncommitted changes and recent commit diffs."""
        try:
            # 1. Uncommitted changes (staged + unstaged)
            proc_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            files: Set[str] = set()
            for line in proc_status.stdout.splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    files.add(parts[1].replace("\\", "/"))

            # 2. Diff against HEAD if available
            proc_diff = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc_diff.returncode == 0:
                for line in proc_diff.stdout.splitlines():
                    if line.strip():
                        files.add(line.strip().replace("\\", "/"))

            return sorted(list(files))
        except Exception:
            # Fallback: assume all if git fails
            return ["backend/app/", "frontend/src/"]

    def analyze(self, changed_files: list[str] | None = None) -> ImpactAnalysisResult:
        if changed_files is None:
            changed_files = self.get_changed_files()

        run_lint = False
        run_backend_unit = False
        run_blender_3d = False
        run_control_plane = False
        run_frontend = False

        for f in changed_files:
            # Python backend files
            if f.startswith("backend/") or f.endswith(".py"):
                run_lint = True
                run_backend_unit = True

                # 3D Blender geometry pipeline changes
                if any(
                    token in f
                    for token in (
                        "decal_baker",
                        "mesh_cleanup",
                        "blender",
                        "harness_blender",
                        "reconstruction",
                    )
                ):
                    run_blender_3d = True

                # Control plane and worker integration changes
                if any(
                    token in f
                    for token in (
                        "worker",
                        "control_plane",
                        "harness_control_plane",
                        "storage",
                    )
                ):
                    run_control_plane = True

            # Frontend files
            if f.startswith("frontend/"):
                run_frontend = True

            # Harness core files
            if f.startswith("harness/"):
                run_lint = True
                run_backend_unit = True

        # If no specific files detected, default to running fast suites
        if not changed_files:
            run_lint = True
            run_backend_unit = True

        return ImpactAnalysisResult(
            changed_files=changed_files,
            run_lint=run_lint,
            run_backend_unit=run_backend_unit,
            run_blender_3d=run_blender_3d,
            run_control_plane=run_control_plane,
            run_frontend=run_frontend,
        )
