#!/usr/bin/env python3
"""Compile the optional CUDA benchmark; fail with an actionable message if nvcc is absent."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NVCC = shutil.which("nvcc")
if not NVCC:
    print("nvcc was not found on PATH. CUDA source is ready to build on a CUDA Toolkit host.", file=sys.stderr)
    raise SystemExit(2)

BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)
output = BUILD / ("gpu_bench.exe" if sys.platform == "win32" else "gpu_bench")
subprocess.run([NVCC, "-O3", "-std=c++17", str(ROOT / "src/cuda/matmul.cu"), "-lcublas", "-o", str(output)], cwd=ROOT, check=True)
print(f"Built {output}")
