#!/usr/bin/env python3
"""Run C++ CPU timings and attach locally detected host metadata."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build" / ("cpu_bench.exe" if sys.platform == "win32" else "cpu_bench")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    cpu = platform.processor() or platform.machine()
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except (ImportError, OSError):
            pass
    sizes = "32,64,128" if args.quick else "128,256,512,1024"
    tiles = "8,16,32" if args.quick else "8,16,32,64"
    repeats = "3" if args.quick else "5"
    command = [str(EXE), "--sizes", sizes, "--tile-sizes", tiles, "--repeats", repeats,
               "--output", str(ROOT / "results/cpu_results.csv"), "--cpu-name", cpu]
    subprocess.run(command, cwd=ROOT, check=True)
    print(f"CPU results saved; processor string: {cpu}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
