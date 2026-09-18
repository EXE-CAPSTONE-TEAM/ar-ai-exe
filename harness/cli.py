"""Unified CLI runner for the ar-ai-exe Enterprise Harness Platform."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from harness.doctor import print_report, run_diagnostics
from harness.linters.architectural_rules import ArchitecturalRulesScanner
from harness.telemetry.context import TelemetryEngine
from harness.tia import TestImpactAnalyzer


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
MOBILE_DIR = REPO_ROOT / "mobile"
PYTHON_BIN = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON_BIN.is_file():
    PYTHON_BIN = Path(sys.executable)
FLUTTER_BIN = shutil.which("flutter") or shutil.which("flutter.bat")


def run_command_with_telemetry(cmd: list[str], cwd: Path, name: str, telemetry: TelemetryEngine) -> bool:
    with telemetry.trace_scope(name, attributes={"command": " ".join(cmd), "cwd": str(cwd)}) as span:
        print(f"\n--> Running [{name}] (Trace ID: {span.trace_id[:8]}...)")
        proc = subprocess.run(cmd, cwd=str(cwd))
        if proc.returncode != 0:
            raise RuntimeError(f"Suite [{name}] failed with exit code {proc.returncode}")
        return True


def run_architectural_linter(telemetry: TelemetryEngine) -> bool:
    with telemetry.trace_scope("architectural_rules_lint") as span:
        print(f"\n--> Running [Mechanical Architectural Rules Linter] (Trace ID: {span.trace_id[:8]}...)")
        scanner = ArchitecturalRulesScanner(REPO_ROOT)
        violations = scanner.scan_all()
        if violations:
            print(f"\033[91mFound {len(violations)} architectural rule violations:\033[0m")
            for v in violations:
                print(f"  [{v.rule_id}] {v.file_path.name}:{v.line_number}")
                print(f"    Issue: {v.message}")
                print(f"    Fix:   {v.remediation}")
            raise RuntimeError("Mechanical linter checks failed.")
        print("\033[92m[OK] 0 architectural rule violations detected.\033[0m")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m harness",
        description="ar-ai-exe Enterprise Harness Engineering Tool",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # Command: doctor
    subparsers.add_parser("doctor", help="Run system and toolchain environment diagnostics.")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Execute harness test suites.")
    run_parser.add_argument(
        "--suite",
        choices=["all", "lint", "blender", "control-plane", "backend", "mobile", "fast"],
        default="all",
        help="Target suite to execute.",
    )
    run_parser.add_argument(
        "--tia",
        action="store_true",
        help="Use Test Impact Analysis to run only tests impacted by current git diff.",
    )

    args = parser.parse_args()

    if args.subcommand == "doctor":
        results = run_diagnostics(REPO_ROOT)
        ok = print_report(results)
        sys.exit(0 if ok else 1)

    if args.subcommand == "run":
        telemetry = TelemetryEngine()
        start_time = time.time()
        failures = []

        suites_to_run = []
        if args.tia:
            analyzer = TestImpactAnalyzer(REPO_ROOT)
            impact = analyzer.analyze()
            print(f"\n[TIA] Changed files detected: {len(impact.changed_files)}")
            print(f"[TIA] Recommended suites: {impact.summary()}")
            if impact.run_lint:
                suites_to_run.append("lint")
            if impact.run_backend_unit:
                suites_to_run.append("backend")
            if impact.run_control_plane:
                suites_to_run.append("control-plane")
            if impact.run_blender_3d:
                suites_to_run.append("blender")
            if impact.run_mobile:
                suites_to_run.append("mobile")
        else:
            if args.suite == "fast":
                suites_to_run = ["lint", "backend", "control-plane"]
            elif args.suite == "all":
                suites_to_run = ["lint", "control-plane", "blender", "backend", "mobile"]
            else:
                suites_to_run = [args.suite]

        print("=" * 65)
        print(f"       AR-AI-EXE ENTERPRISE HARNESS RUNNER (Suites: {', '.join(suites_to_run)})")
        print("=" * 65)

        for suite in suites_to_run:
            try:
                if suite == "lint":
                    run_architectural_linter(telemetry)
                elif suite == "blender":
                    run_command_with_telemetry(
                        [str(PYTHON_BIN), "-m", "pytest", "tests/harness_blender/", "-v"],
                        cwd=BACKEND_DIR,
                        name="Blender_Headless_3D_Suite",
                        telemetry=telemetry,
                    )
                elif suite == "control-plane":
                    run_command_with_telemetry(
                        [str(PYTHON_BIN), "-m", "pytest", "tests/harness_control_plane/", "-v"],
                        cwd=BACKEND_DIR,
                        name="Control_Plane_Mock_Storage_Suite",
                        telemetry=telemetry,
                    )
                elif suite == "backend":
                    run_command_with_telemetry(
                        [str(PYTHON_BIN), "-m", "pytest", "tests/test_architectural_linter.py", "tests/test_telemetry_context.py", "-v"],
                        cwd=BACKEND_DIR,
                        name="Backend_Harness_Meta_Suite",
                        telemetry=telemetry,
                    )
                elif suite == "mobile":
                    if not FLUTTER_BIN:
                        raise RuntimeError("Flutter binary not found on PATH.")
                    run_command_with_telemetry(
                        [str(FLUTTER_BIN), "analyze"],
                        cwd=MOBILE_DIR,
                        name="Mobile_Flutter_Analyze_Suite",
                        telemetry=telemetry,
                    )
                    run_command_with_telemetry(
                        [str(FLUTTER_BIN), "test"],
                        cwd=MOBILE_DIR,
                        name="Mobile_Flutter_Test_Suite",
                        telemetry=telemetry,
                    )
            except Exception as exc:
                failures.append((suite, str(exc)))

        duration = time.time() - start_time
        print("\n" + "=" * 65)
        if not failures:
            print(f"\033[92mALL HARNESS SUITES PASSED ({duration:.2f}s)\033[0m")
            print("=" * 65 + "\n")
            sys.exit(0)
        else:
            print(f"\033[91mHARNESS RUN FAILED with {len(failures)} failed suites ({duration:.2f}s):\033[0m")
            for name, err in failures:
                print(f"  - {name}: {err}")
            print("=" * 65 + "\n")
            sys.exit(1)

    parser.print_help()


if __name__ == "__main__":
    main()
