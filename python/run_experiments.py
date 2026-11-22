#!/usr/bin/env python3
"""Run trace-driven cache experiments and save only measured simulator output."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build" / ("cache_sim.exe" if sys.platform == "win32" else "cache_sim")
OUT = ROOT / "results"
BASE = dict(cache_bytes=32768, line_bytes=64, ways=8, policy="lru")


def run_one(experiment: str, n: int, pattern: str, tile: int, *, cache_bytes: int, line_bytes: int,
            ways: int | str, policy: str = "lru", classify: bool = False) -> dict:
    command = [str(EXE), "--n", str(n), "--pattern", pattern, "--tile", str(tile), "--cache-size", str(cache_bytes),
               "--line-size", str(line_bytes), "--ways", str(ways), "--policy", policy, "--format", "json"]
    if classify:
        command.append("--classify")
    start = time.perf_counter()
    result = subprocess.run(command, check=True, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    row = json.loads(result.stdout)
    row.update(experiment=experiment, simulator_seconds=elapsed)
    # Illustrative model only: 4-cycle hit plus a 200-cycle miss penalty.
    row["amat_cycles_illustrative"] = 4.0 + row["miss_rate"] * 200.0
    print(f"{experiment}: N={n} {pattern} T={tile}, cache={cache_bytes}/{line_bytes}/{ways}: "
          f"{row['misses']:,}/{row['accesses']:,} misses", flush=True)
    return row


def write_csv(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="run the short validation-sized sweep")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    ns = [64, 128] if args.quick else [64, 128, 256, 512]
    patterns = ["naive", "ikj", "tiled"]
    tiles = [4, 8, 16, 32] if args.quick else [4, 8, 16, 32, 64, 128]
    # The quick sweep focuses tile size at N=64 and N=128; the full sweep covers each requested N.
    b_ns = ns if not args.quick else [64, 128]
    b_rows = [run_one("B", n, "tiled", tile, **BASE) for n in b_ns for tile in tiles]
    write_csv("cache_exp_b.csv", b_rows)
    best_tiles = {}
    for n in b_ns:
        candidates = [row for row in b_rows if row["n"] == n]
        best_tiles[n] = min(candidates, key=lambda row: (row["miss_rate"], row["tile"]))["tile"]
    default_tile = min(best_tiles.values()) if best_tiles else 16
    a_rows = [run_one("A", n, pattern, best_tiles.get(n, default_tile), **BASE) for n in ns for pattern in patterns]
    write_csv("cache_exp_a.csv", a_rows)

    c_n = 128 if args.quick else 256
    c_tile = best_tiles.get(c_n, default_tile)
    cache_sizes = [8192, 16384, 32768, 65536, 131072] if args.quick else [8192, 16384, 32768, 65536, 131072, 262144]
    c_rows = [run_one("C", c_n, pattern, c_tile, cache_bytes=size, line_bytes=64, ways=8)
              for size in cache_sizes for pattern in ("naive", "tiled")]
    write_csv("cache_exp_c.csv", c_rows)

    # Keep the same fixed N across modes; full associativity scans all lines in this simple flat-array core.
    d_n = 64
    d_tile = best_tiles.get(d_n, default_tile)
    assoc_values: list[int | str] = [1, 2, 4, 8, "fully"]
    d_assoc = [run_one("D-associativity", d_n, pattern, d_tile, cache_bytes=32768, line_bytes=64, ways=ways)
               for ways in assoc_values for pattern in ("naive", "tiled")]
    d_lines = [run_one("D-line-size", d_n, pattern, d_tile, cache_bytes=32768, line_bytes=line, ways=8)
               for line in (32, 64, 128) for pattern in ("naive", "tiled")]
    write_csv("cache_exp_d.csv", d_assoc + d_lines)

    # The quick sweep compares 128 with a nearby padded stride (132); full uses the requested 512/520 case.
    conflict_ns = [128, 132] if args.quick else [512, 520]
    conflict_tile = best_tiles.get(conflict_ns[0], default_tile)
    conflict_rows = [run_one("D-conflict", n, pattern, conflict_tile, **BASE)
                     for n in conflict_ns for pattern in ("naive", "tiled")]
    write_csv("cache_conflict_case.csv", conflict_rows)

    e_n = 64 if args.quick else 256
    e_tile = best_tiles.get(e_n, default_tile)
    e_rows = [run_one("E", e_n, pattern, e_tile, classify=True, **BASE) for pattern in ("naive", "tiled")]
    write_csv("cache_exp_e.csv", e_rows)

    all_rows = a_rows + b_rows + c_rows + d_assoc + d_lines + conflict_rows + e_rows
    write_csv("cache_results.csv", all_rows)
    meta = {
        "mode": "quick" if args.quick else "full",
        "machine": "results are from the local executable; CPU timings are recorded separately",
        "cache_baseline": BASE,
        "tile_loop_order": "ii,kk,jj,i,k,j",
        "best_simulated_tile_by_n": best_tiles,
        "amat_example": {"hit_cycles": 4, "miss_penalty_cycles": 200, "measured": False},
    }
    (OUT / "experiment_metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
