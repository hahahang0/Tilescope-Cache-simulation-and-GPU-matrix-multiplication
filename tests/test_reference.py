from __future__ import annotations

import json
import os
import csv
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from cache_reference import simulate

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build" / ("cache_sim.exe" if os.name == "nt" else "cache_sim")


class SimulatorCrossCheck(unittest.TestCase):
    def test_random_traces_match_python_reference(self):
        rng = random.Random(20261121)
        validation = []
        for policy in ("lru", "fifo"):
            for seed in range(8):
                local = random.Random(rng.randrange(1 << 30) + seed)
                operations = [local.choice("RRRWW") for _ in range(500)]
                addresses = [local.randrange(0, 160) * 8 + local.randrange(8) for _ in operations]
                with tempfile.NamedTemporaryFile("w", delete=False, suffix=".trace") as trace:
                    path = Path(trace.name)
                    for op, address in zip(operations, addresses):
                        trace.write(f"{op} 0x{address:x}\n")
                try:
                    proc = subprocess.run(
                        [str(EXE), "--trace", str(path), "--cache-size", "256", "--line-size", "16",
                         "--ways", "2", "--policy", policy, "--format", "json", "--classify"],
                        cwd=ROOT, check=True, capture_output=True, text=True,
                    )
                finally:
                    path.unlink(missing_ok=True)
                actual = json.loads(proc.stdout)
                expected = simulate(addresses, operations, 256, 16, 2, policy)
                for key, value in expected.items():
                    self.assertEqual(actual[key], value, f"{policy}, random trace {seed}, field {key}")
                self.assertEqual(actual["misses"], actual["compulsory"] + actual["capacity"] + actual["conflict"])
                validation.append({"policy": policy, "seed": seed, "accesses": len(addresses), "passed": True,
                                   "hits": actual["hits"], "misses": actual["misses"]})
        output = ROOT / "results" / "validation_random_crosscheck.csv"
        with output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(validation[0]))
            writer.writeheader()
            writer.writerows(validation)


if __name__ == "__main__":
    unittest.main()
