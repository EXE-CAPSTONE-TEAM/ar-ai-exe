"""Environment and toolchain diagnostic utility for ar-ai-exe harness."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


KNOWN_WINDOWS_BLENDER_PATHS = [
    Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"),
]


@dataclass
class DiagnosticResult:
    name: str
    status: str  # "OK", "WARN", "FAIL"
    details: str
    path: Optional[str] = None


def find_blender_binary() -> Optional[Path]:
    """Locate Blender executable via env var, PATH, or standard installation paths."""
    # 1. Check environment variable
    env_blender = os.environ.get("BLENDER_BIN")
    if env_blender and Path(env_blender).is_file():
        return Path(env_blender)

    # 2. Check system PATH
    which_blender = shutil.which("blender")
    if which_blender:
        return Path(which_blender)

    # 3. Check known Windows paths
    if sys.platform == "win32":
        for candidate in KNOWN_WINDOWS_BLENDER_PATHS:
            if candidate.is_file():
                return candidate

    return None


def check_python() -> DiagnosticResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        return DiagnosticResult("Python", "OK", f"Python {version} ({sys.executable})", sys.executable)
    return DiagnosticResult("Python", "WARN", f"Python {version} (Recommended: 3.11+)", sys.executable)


def check_blender() -> DiagnosticResult:
    binary = find_blender_binary()
    if not binary:
        return DiagnosticResult(
            "Blender",
            "WARN",
            "Blender not found. Headless 3D tests will be skipped. "
            "Set BLENDER_BIN env var or install Blender 4.x/5.x.",
        )

    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "Blender (Unknown Version)"
        return DiagnosticResult("Blender", "OK", f"{first_line} at {binary}", str(binary))
    except Exception as exc:
        return DiagnosticResult("Blender", "WARN", f"Failed to execute Blender: {exc}", str(binary))


def check_node() -> DiagnosticResult:
    node_bin = shutil.which("node")
    if not node_bin:
        return DiagnosticResult("Node.js", "WARN", "Node.js not found on PATH.")
    try:
        proc = subprocess.run([node_bin, "--version"], capture_output=True, text=True, timeout=5, check=True)
        return DiagnosticResult("Node.js", "OK", f"Node {proc.stdout.strip()} ({node_bin})", node_bin)
    except Exception as exc:
        return DiagnosticResult("Node.js", "WARN", f"Error checking node: {exc}", node_bin)


def check_npm() -> DiagnosticResult:
    npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_bin:
        return DiagnosticResult("NPM", "WARN", "NPM not found on PATH.")
    try:
        proc = subprocess.run([npm_bin, "--version"], capture_output=True, text=True, timeout=5, check=True)
        return DiagnosticResult("NPM", "OK", f"npm v{proc.stdout.strip()} ({npm_bin})", npm_bin)
    except Exception as exc:
        return DiagnosticResult("NPM", "WARN", f"Error checking npm: {exc}", npm_bin)


def check_test_assets(repo_root: Path) -> DiagnosticResult:
    model_path = repo_root / "data" / "3DModel.glb"
    if model_path.is_file():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        return DiagnosticResult(
            "3D Test Assets",
            "OK",
            f"Found standard model {model_path.name} ({size_mb:.2f} MB)",
            str(model_path),
        )
    return DiagnosticResult(
        "3D Test Assets",
        "WARN",
        "data/3DModel.glb missing. Procedural fixtures will be used exclusively.",
    )


def run_diagnostics(repo_root: Optional[Path] = None) -> list[DiagnosticResult]:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]

    results = [
        check_python(),
        check_blender(),
        check_node(),
        check_npm(),
        check_test_assets(repo_root),
    ]
    return results


def print_report(results: list[DiagnosticResult]) -> bool:
    print("\n" + "=" * 60)
    print("           AR-AI-EXE HARNESS SYSTEM DIAGNOSTICS")
    print("=" * 60)
    all_ok = True
    for r in results:
        badge = f"[{r.status}]"
        if r.status == "OK":
            color_badge = f"\033[92m{badge:<6}\033[0m"
        elif r.status == "WARN":
            color_badge = f"\033[93m{badge:<6}\033[0m"
        else:
            color_badge = f"\033[91m{badge:<6}\033[0m"
            all_ok = False
        print(f"{color_badge} {r.name:<18} : {r.details}")
    print("=" * 60 + "\n")
    return all_ok


if __name__ == "__main__":
    results = run_diagnostics()
    print_report(results)
