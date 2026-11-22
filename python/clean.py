#!/usr/bin/env python3
"""Remove only generated build and experiment artifacts."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
if BUILD.exists():
    for item in BUILD.iterdir():
        if item.is_file():
            item.unlink()

generated = [
    "cache_results.csv", "cache_exp_a.csv", "cache_exp_b.csv", "cache_exp_c.csv",
    "cache_exp_d.csv", "cache_exp_e.csv", "cache_conflict_case.csv", "cpu_results.csv",
    "gpu_results.csv", "experiment_metadata.json", "performance_500m.csv", "ncu_naive.ncu-rep", "ncu_tiled.ncu-rep",
    "validation_results.csv", "validation_random_crosscheck.csv",
]
for name in generated:
    (ROOT / "results" / name).unlink(missing_ok=True)
for item in (ROOT / "figures").glob("*"):
    if item.is_file() and item.suffix.lower() in {".png", ".pdf"}:
        item.unlink()
(ROOT / "report" / "tilescope_report.pdf").unlink(missing_ok=True)
