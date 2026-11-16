#!/usr/bin/env python3
"""NeuroOptic One-Click Starter (PRINCIPLE-011).

Provides instant, zero-friction startup for the NeuroOptic visual entrainment
system. Supports 1-click GUI launching, direct safe quick-start sessions
(40Hz Gamma, 10Hz Alpha), headless dry-runs, and environment verification.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from typing import List, Tuple

REQUIRED_MODULES = [
    ("glfw", "glfw"),
    ("OpenGL", "PyOpenGL"),
    ("numpy", "numpy"),
    ("customtkinter", "customtkinter"),
]


def check_dependencies() -> Tuple[bool, List[str]]:
    """Check if all runtime dependencies are importable."""
    missing = []
    for mod_name, pkg_name in REQUIRED_MODULES:
        if importlib.util.find_spec(mod_name) is None:
            missing.append(pkg_name)
    return len(missing) == 0, missing


def print_remediation_error(what: str, why: str, fix: str) -> None:
    """Print actionable remediation triad adhering to PRINCIPLE-011 R6."""
    sys.stderr.write(f"Error: {what}\n")
    sys.stderr.write(f"Why: {why}\n")
    sys.stderr.write(f"Fix: {fix}\n")


def build_quick_command(preset: str = "gamma", dry_run: bool = False) -> List[str]:
    """Construct safe entrainment command for one-click start."""
    engine_path = os.path.join(os.path.dirname(__file__), "entrainment_engine.py")
    freq = "10.0" if preset.lower() == "alpha" else "40.0"
    cmd = [
        sys.executable,
        engine_path,
        "--freq", freq,
        "--waveform", "sine",
        "--mode", "full",
        "--ramp", "5.0",
        "--sham", "none",
    ]
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="NeuroOptic One-Click Starter - Instant visual entrainment launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python start.py            # Launch the GUI controller
  python start.py --quick    # 1-click start safe 40Hz Gamma entrainment
  python start.py --alpha    # 1-click start safe 10Hz Alpha entrainment
  python start.py --dry-run  # Validate configuration without opening windows
  python start.py --check    # Verify runtime dependencies
"""
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick-start safe 40Hz Gamma session directly"
    )
    parser.add_argument(
        "--alpha", "-a",
        action="store_true",
        help="Quick-start safe 10Hz Alpha session directly"
    )
    parser.add_argument(
        "--gui", "-g",
        action="store_true",
        help="Launch the GUI controller (default behavior)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Validate parameters and dependencies without displaying windows"
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check dependencies and system readiness without starting"
    )

    args = parser.parse_args()

    # 1. Dependency verification
    ok, missing = check_dependencies()
    if not ok:
        print_remediation_error(
            what="NeuroOptic runtime dependencies are missing.",
            why=f"Required package(s) not found in Python environment: {', '.join(missing)}.",
            fix=f"Run '{sys.executable} -m pip install -r requirements.txt' to install dependencies."
        )
        return 1

    if args.check:
        print("NeuroOptic Environment Status: READY")
        print("All declared dependencies are installed.")
        return 0

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. Direct Safe Session Launch (--quick / --alpha)
    if args.quick or args.alpha or (args.dry_run and not args.gui):
        preset = "alpha" if args.alpha else "gamma"
        cmd = build_quick_command(preset=preset, dry_run=args.dry_run)
        if args.dry_run:
            print(f"[DRY RUN] Would execute safe {preset.upper()} entrainment:")
            print(" ".join(cmd))
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                print_remediation_error(
                    what="Dry-run validation failed.",
                    why=proc.stderr.strip() or "Engine dry-run returned non-zero code.",
                    fix="Verify entrainment_engine.py arguments and system configuration."
                )
                return 1
            print("[OK] Protocol and engine parameters verified successfully.")
            return 0

        # Live engine session launch
        try:
            proc = subprocess.Popen(cmd)  # hygiene: allow fire-and-forget launch; the engine must outlive the launcher
            return 0
        except Exception as exc:
            print_remediation_error(
                what="Failed to launch entrainment engine.",
                why=str(exc),
                fix="Ensure graphics drivers and GLFW libraries are installed."
            )
            return 1

    # 3. GUI Launch (Default)
    launcher_path = os.path.join(base_dir, "launcher.py")
    cmd = [sys.executable, launcher_path]
    try:
        proc = subprocess.Popen(cmd)  # hygiene: allow fire-and-forget launch; the launcher process handles UI loop
        return 0
    except Exception as exc:
        print_remediation_error(
            what="Failed to launch NeuroOptic Controller GUI.",
            why=str(exc),
            fix="Ensure tkinter/customtkinter are supported on your platform."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
