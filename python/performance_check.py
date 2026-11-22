#!/usr/bin/env python3
"""Time one 500-million-event simulation and save the measured result."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build" / ("cache_sim.exe" if sys.platform == "win32" else "cache_sim")
command = [str(EXE), "--n", "500", "--pattern", "ikj", "--tile", "16", "--format", "json"]
start = time.perf_counter()
completed = subprocess.run(command, check=True, capture_output=True, text=True, cwd=ROOT)
elapsed = time.perf_counter() - start
row = json.loads(completed.stdout)
row["elapsed_seconds"] = elapsed
path = ROOT / "results" / "performance_500m.csv"
with path.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
print(f"500,000,000 accesses in {elapsed:.3f} seconds; saved {path}")
