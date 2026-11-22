#!/usr/bin/env python3
"""Portable g++ build and test driver used by the Makefile."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
CXX = os.environ.get("CXX", "g++")
FLAGS = ["-std=c++17", "-O3", "-Wall", "-Wextra", "-pedantic"]
SUFFIX = ".exe" if os.name == "nt" else ""


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def compile_one(output: str, sources: list[str]) -> Path:
    target = BUILD / f"{output}{SUFFIX}"
    BUILD.mkdir(exist_ok=True)
    run([CXX, *FLAGS, "-I", str(ROOT / "src/cache_sim"), *[str(ROOT / source) for source in sources], "-o", str(target)])
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["build", "test", "clean"], default="build")
    args = parser.parse_args()
    if args.target == "clean":
        for path in BUILD.glob(f"*{SUFFIX}"):
            path.unlink()
        return 0
    compile_one("cache_sim", ["src/cache_sim/cache_sim.cpp", "src/cache_sim/main.cpp"])
    compile_one("cpu_bench", ["src/cpu_bench/main.cpp"])
    if args.target == "test":
        compile_one("test_cache", ["src/cache_sim/cache_sim.cpp", "tests/test_cache.cpp"])
        run([str(BUILD / f"test_cache{SUFFIX}")])
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
