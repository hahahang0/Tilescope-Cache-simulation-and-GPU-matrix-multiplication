#!/usr/bin/env python3
"""Run the compiled CUDA benchmark with platform-correct executable paths."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build" / ("gpu_bench.exe" if sys.platform == "win32" else "gpu_bench")
subprocess.run([str(EXE), "--output", str(ROOT / "results/gpu_results.csv")], cwd=ROOT, check=True)
