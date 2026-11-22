#!/usr/bin/env python3
"""Create report figures from the measured CSV files in results/."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


def read_rows(name: str) -> list[dict]:
    path = RESULTS / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURES / f"{name}.png", dpi=180, bbox_inches="tight")
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_cache() -> None:
    FIGURES.mkdir(exist_ok=True)
    rows = read_rows("cache_exp_a.csv")
    if rows:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        for pattern in ("naive", "ikj", "tiled"):
            selected = sorted((r for r in rows if r["pattern"] == pattern), key=lambda r: int(r["n"]))
            ax.plot([int(r["n"]) for r in selected], [100 * float(r["miss_rate"]) for r in selected], marker="o", label=pattern)
        ax.set(title="Cache miss rate by matrix size", xlabel="Matrix dimension N (float32, row-major)", ylabel="Miss rate (%)")
        ax.grid(True, alpha=.25); ax.legend(title="Access order")
        save(fig, "miss_rate_vs_n")

    rows = read_rows("cache_exp_b.csv")
    if rows:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        for n in sorted({int(r["n"]) for r in rows}):
            selected = sorted((r for r in rows if int(r["n"]) == n), key=lambda r: int(r["tile"]))
            ax.plot([int(r["tile"]) for r in selected], [100 * float(r["miss_rate"]) for r in selected], marker="o", label=f"N={n}")
        ax.set(title="Tiled miss rate versus tile size", xlabel="Tile width T (elements)", ylabel="Miss rate (%)")
        ax.grid(True, alpha=.25); ax.legend(title="Matrix size")
        save(fig, "miss_rate_vs_tile")

    rows = read_rows("cache_exp_c.csv")
    if rows:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        for pattern in ("naive", "tiled"):
            selected = sorted((r for r in rows if r["pattern"] == pattern), key=lambda r: int(r["cache_bytes"]))
            ax.plot([int(r["cache_bytes"]) / 1024 for r in selected], [100 * float(r["miss_rate"]) for r in selected], marker="o", label=pattern)
        ax.set_xscale("log", base=2)
        ax.set(title="Cache capacity sensitivity", xlabel="Cache capacity (KiB; 64-byte lines, 8-way)", ylabel="Miss rate (%)")
        ax.grid(True, which="both", alpha=.25); ax.legend(title="Access order")
        save(fig, "miss_rate_vs_cache_size")

    rows = read_rows("cache_exp_d.csv")
    assoc = [r for r in rows if r["experiment"] == "D-associativity"]
    if assoc:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        for pattern in ("naive", "tiled"):
            selected = [r for r in assoc if r["pattern"] == pattern]
            selected.sort(key=lambda r: int(r["ways"]))
            labels = ["Fully" if int(r["ways"]) == int(r["cache_bytes"]) // int(r["line_bytes"]) else r["ways"] for r in selected]
            ax.plot(labels, [100 * float(r["miss_rate"]) for r in selected], marker="o", label=pattern)
        ax.set(title="Associativity sensitivity", xlabel="Ways (fully associative at right)", ylabel="Miss rate (%)")
        ax.grid(True, alpha=.25); ax.legend(title="Access order")
        save(fig, "miss_rate_vs_associativity")

    lines = [r for r in rows if r["experiment"] == "D-line-size"]
    if lines:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        for pattern in ("naive", "tiled"):
            selected = sorted((r for r in lines if r["pattern"] == pattern), key=lambda r: int(r["line_bytes"]))
            ax.plot([int(r["line_bytes"]) for r in selected], [100 * float(r["miss_rate"]) for r in selected], marker="o", label=pattern)
        ax.set(title="Cache line-size sensitivity", xlabel="Cache line size (bytes)", ylabel="Miss rate (%)")
        ax.grid(True, alpha=.25); ax.legend(title="Access order")
        save(fig, "miss_rate_vs_line_size")

    rows = read_rows("cache_conflict_case.csv")
    if rows:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        labels = sorted({int(r["n"]) for r in rows})
        width = .36
        for index, pattern in enumerate(("naive", "tiled")):
            selected = sorted((r for r in rows if r["pattern"] == pattern), key=lambda r: int(r["n"]))
            ax.bar([x + (index - .5) * width for x in range(len(labels))], [100 * float(r["miss_rate"]) for r in selected], width, label=pattern)
        ax.set_xticks(range(len(labels)), [str(n) for n in labels])
        ax.set(title="Power-of-two and padded leading dimensions", xlabel="Matrix dimension N", ylabel="Miss rate (%)")
        ax.grid(True, axis="y", alpha=.25); ax.legend(title="Access order")
        save(fig, "power2_vs_padded_stride")

    rows = read_rows("cache_exp_e.csv")
    if rows:
        fig, ax = plt.subplots(figsize=(7.4, 4.5))
        categories = [("compulsory", "Compulsory"), ("capacity", "Capacity"), ("conflict", "Conflict")]
        bottom = [0.0] * len(rows)
        for field, label in categories:
            vals = [int(r[field]) for r in rows]
            ax.bar([r["pattern"] for r in rows], vals, bottom=bottom, label=label)
            bottom = [a + b for a, b in zip(bottom, vals)]
        ax.set(title="3C classification for baseline cache", xlabel="Access order", ylabel="Classified misses (count)")
        ax.legend(); ax.grid(True, axis="y", alpha=.25)
        save(fig, "miss_classification")


def plot_cpu() -> None:
    rows = read_rows("cpu_results.csv")
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    for algorithm in ("naive", "ikj", "tiled"):
        selected = [r for r in rows if r["algorithm"] == algorithm]
        grouped = {}
        for row in selected:
            n = int(row["n"])
            grouped.setdefault(n, []).append(float(row["gflops"]))
        ns = sorted(grouped)
        values = [max(grouped[n]) for n in ns]
        ax.plot(ns, values, marker="o", label=algorithm)
    ax.set(title="CPU matrix multiplication throughput", xlabel="Matrix dimension N", ylabel="GFLOP/s (median timing)")
    ax.grid(True, alpha=.25); ax.legend(title="Implementation; best tiled T")
    save(fig, "cpu_gflops_vs_n")


def plot_gpu() -> None:
    rows = read_rows("gpu_results.csv")
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    for algorithm in ("naive", "tiled", "cublas"):
        selected = [r for r in rows if r["algorithm"] == algorithm]
        grouped = {}
        for row in selected:
            grouped.setdefault(int(row["n"]), []).append(float(row["gflops"]))
        ns = sorted(grouped)
        if ns:
            ax.plot(ns, [max(grouped[n]) for n in ns], marker="o", label=algorithm)
    ax.set(title="Measured GPU matrix multiplication throughput", xlabel="Matrix dimension N", ylabel="GFLOP/s (median CUDA-event timing)")
    ax.grid(True, alpha=.25); ax.legend(title="Kernel")
    save(fig, "gpu_gflops_vs_n")


def make_diagram(name: str, draw) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 3.5))
    ax.set_xlim(0, 10); ax.set_ylim(0, 4); ax.axis("off")
    draw(ax)
    save(fig, name)


def plot_teaching_diagrams() -> None:
    FIGURES.mkdir(exist_ok=True)

    def hierarchy(ax):
        labels = ["Registers", "Shared memory / L1", "L2 cache", "Global memory (DRAM)"]
        colors = ["#315a8a", "#4f83b5", "#80b1d3", "#c6d8e8"]
        for i, (label, color) in enumerate(zip(labels, colors)):
            y = 3.35 - i * .82
            ax.add_patch(Rectangle((1.4, y), 7.2, .52, facecolor=color, edgecolor="#203040", linewidth=1.2))
            ax.text(5, y + .26, label, ha="center", va="center", color="white" if i < 2 else "#17232d", fontsize=11, weight="bold")
        ax.text(.45, 3.6, "Smaller\n/faster", va="center", ha="center", fontsize=9)
        ax.text(.45, .85, "Larger\n/slower", va="center", ha="center", fontsize=9)
        ax.annotate("capacity generally grows", xy=(9.35, .8), xytext=(9.35, 3.7), arrowprops=dict(arrowstyle="->", lw=1.5), rotation=90, ha="center", va="center", fontsize=9)
    make_diagram("memory_hierarchy", hierarchy)

    def address(ax):
        ax.text(5, 3.72, "32-bit example address: 0x00001234", ha="center", va="center", fontsize=12, weight="bold")
        fields = [(0.5, 20, "Tag: 20 bits\n0x1", "#8fb9d9"), (6.2, 6, "Set index\n6 bits = 8", "#f2c879"), (8.05, 6, "Byte offset\n6 bits = 52", "#a6d6a8")]
        for x, width, label, color in fields:
            w = width / 32 * 9
            ax.add_patch(Rectangle((x, 2.3), w, .83, facecolor=color, edgecolor="#203040", linewidth=1.3))
            ax.text(x + w / 2, 2.72, label, ha="center", va="center", fontsize=9, weight="bold")
        ax.text(5, 1.68, "32 KiB cache · 64-byte lines · 8 ways → 64 sets", ha="center", fontsize=10)
        ax.text(5, 1.08, "Address = [ tag | set index | byte offset ]", ha="center", fontsize=11)
        ax.text(5, .45, "0x1234: offset = 0x34 = 52; index = 8; tag = 1", ha="center", fontsize=10)
    make_diagram("address_decomposition", address)

    def coalescing(ax):
        ax.text(5, 3.75, "Adjacent lanes access adjacent float32 elements of B", ha="center", va="center", fontsize=12, weight="bold")
        colors = ["#cde5f5", "#b8d8ed", "#a4cbe3", "#8fb9d9"]
        for lane in range(4):
            x = 1.1 + lane * 2.0
            ax.add_patch(Rectangle((x, 2.2), 1.55, .58, facecolor=colors[lane], edgecolor="#203040"))
            ax.text(x + .775, 2.49, f"lane {lane}", ha="center", va="center", fontsize=10)
            ax.text(x + .775, 1.72, f"B[k, j+{lane}]", ha="center", va="center", fontsize=9)
            ax.text(x + .775, 1.2, f"+{4*lane} bytes", ha="center", va="center", fontsize=9)
        ax.text(5, .55, "For fixed k: B[k*N + col] varies contiguously with col; A[row,k] is shared by the lanes.", ha="center", fontsize=9)
    make_diagram("gpu_coalescing", coalescing)

    def tiling(ax):
        ax.text(5, 3.77, "One CUDA block computes a T × T output tile", ha="center", fontsize=12, weight="bold")
        for x, y, label, color in [(0.6, 1.9, "A tile\nT × T", "#a8cee5"), (7.7, 1.9, "B tile\nT × T", "#f2cc83"), (4.0, .55, "C output tile\nT × T", "#b9dcb6")]:
            ax.add_patch(Rectangle((x, y), 1.7, 1.0, facecolor=color, edgecolor="#203040", linewidth=1.2))
            ax.text(x + .85, y + .5, label, ha="center", va="center", fontsize=10, weight="bold")
        for start, end in [((2.3, 2.4), (4.1, 1.2)), ((7.7, 2.4), (5.9, 1.2))]:
            ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=14, linewidth=1.5, color="#34495e"))
        ax.text(5, 2.45, "load cooperatively", ha="center", fontsize=9)
        ax.text(5, .23, "sync → multiply-accumulate with shared reuse → sync before loading the next K tile", ha="center", fontsize=9)
    make_diagram("gpu_tiled_kernel", tiling)


def main() -> None:
    plot_cache()
    plot_cpu()
    plot_gpu()
    plot_teaching_diagrams()
    print(f"Figures written under {FIGURES}")


if __name__ == "__main__":
    main()
