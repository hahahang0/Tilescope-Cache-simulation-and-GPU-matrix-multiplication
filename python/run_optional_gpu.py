#!/usr/bin/env python3
"""Build and run CUDA only when the CUDA compiler is available."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not shutil.which("nvcc"):
    print("CUDA experiment skipped: nvcc is unavailable; GPU results remain pending.")
    raise SystemExit(0)
subprocess.run([sys.executable, "python/build_cuda.py"], cwd=ROOT, check=True)
subprocess.run([sys.executable, "python/run_gpu_bench.py"], cwd=ROOT, check=True)
