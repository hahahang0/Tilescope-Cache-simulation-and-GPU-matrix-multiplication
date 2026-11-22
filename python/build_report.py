#!/usr/bin/env python3
"""Build the teaching report from the experiment CSVs and generated figures."""
from __future__ import annotations

import csv
from datetime import datetime
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageTemplate, Paragraph, PageBreak,
                                Spacer, Table, LongTable, TableStyle, KeepTogether)
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
PDF = ROOT / "report" / "tilescope_report.pdf"
NAVY = colors.HexColor("#19324A")
BLUE = colors.HexColor("#386D98")
PALE = colors.HexColor("#EAF1F6")
ORANGE = colors.HexColor("#FFF0D6")
GRAY = colors.HexColor("#55616C")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=26,
                          leading=31, textColor=NAVY, alignment=TA_CENTER, spaceAfter=20))
styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontSize=13, leading=19,
                          textColor=GRAY, alignment=TA_CENTER, spaceAfter=10))
styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17,
                          leading=21, textColor=NAVY, spaceBefore=13, spaceAfter=9, keepWithNext=True))
styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                          leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=6, keepWithNext=True))
styles.add(ParagraphStyle(name="Bodyx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.4,
                          leading=13.5, spaceAfter=7, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="Smallx", parent=styles["BodyText"], fontName="Helvetica", fontSize=8,
                          leading=10.5, textColor=GRAY, spaceAfter=4))
styles.add(ParagraphStyle(name="Captionx", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=8,
                          leading=10, alignment=TA_CENTER, textColor=GRAY, spaceAfter=8))
styles.add(ParagraphStyle(name="Pendingx", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=13,
                          leading=18, textColor=colors.HexColor("#744A00"), alignment=TA_CENTER, spaceAfter=5))
styles.add(ParagraphStyle(name="TableHeadx", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.5,
                          leading=9, textColor=colors.white))
styles.add(ParagraphStyle(name="TableCellx", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.6,
                          leading=9.5))


def read_csv(name: str) -> list[dict]:
    path = RESULTS / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_json(name: str, fallback=None):
    path = RESULTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def P(text: str, style: str = "Bodyx") -> Paragraph:
    return Paragraph(text, styles[style])


def heading(text: str, level: int = 1) -> Paragraph:
    return P(text, "H1x" if level == 1 else "H2x")


def section(title: str, paras: list[str], level: int = 2) -> list:
    output = [heading(title, level)]
    output.extend(P(s) for s in paras)
    return output


def fmt_pct(value: float) -> str:
    return f"{100 * value:.3f}%"


def fmt_int(value) -> str:
    return f"{int(float(value)):,}"


def add_table(story: list, headers: list[str], rows: list[list], widths: list[float] | None = None,
              font_size: float = 7.5) -> None:
    data = [[P(str(h), "TableHeadx") for h in headers]]
    for row in rows:
        data.append([P(str(cell), "TableCellx") for cell in row])
    table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CAD4DD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([table, Spacer(1, 8)])


def figure(story: list, name: str, caption: str) -> None:
    path = FIGURES / f"{name}.png"
    if not path.exists():
        story.append(P(f"Figure not generated: {name}. Run python/plot_results.py.", "Smallx"))
        return
    image = Image(str(path))
    image._restrictSize(6.55 * inch, 4.3 * inch)
    story.append(KeepTogether([image, P(caption, "Captionx")]))


def compiler_version() -> str:
    compiler = shutil.which("g++")
    if not compiler:
        return "g++ version unavailable at report-build time"
    try:
        line = subprocess.run([compiler, "--version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
        return line.strip()
    except Exception:
        return "g++ version unavailable at report-build time"


def results_context(story: list) -> None:
    mode = read_json("experiment_metadata.json", {}).get("mode", "unknown")
    a = read_csv("cache_exp_a.csv")
    b = read_csv("cache_exp_b.csv")
    c = read_csv("cache_exp_c.csv")
    d = read_csv("cache_exp_d.csv")
    conflict = read_csv("cache_conflict_case.csv")
    e = read_csv("cache_exp_e.csv")
    cpu = read_csv("cpu_results.csv")
    story.append(heading("6. Simulator results", 1))
    if not a:
        story.append(P("No cache experiment CSVs were found. Run make quick or make experiments before building the final report."))
        return
    story.append(P(f"The recorded cache sweep mode is <b>{mode}</b>. These are direct outputs from the C++ simulator and are saved in results/. The quick mode uses smaller matrices and fewer parameter points to finish in a few minutes; the full mode runs the requested N values 64, 128, 256, and 512, the complete tile sweep, and the N=512 versus N=520 stride comparison."))
    latest_n = max(int(r["n"]) for r in a)
    latest = {r["pattern"]: r for r in a if int(r["n"]) == latest_n}
    if latest:
        best = min(latest.values(), key=lambda row: float(row["miss_rate"]))
        story.append(P(f"At the largest N present in Exp A (N={latest_n}), the measured lowest miss rate was for <b>{best['pattern']}</b>: {fmt_pct(float(best['miss_rate']))}, from {fmt_int(best['accesses'])} accesses. The comparison below uses the CSV values; it does not assume a hardware timing model."))
    rows = [[int(r["n"]), r["pattern"], int(r["tile"]), fmt_pct(float(r["miss_rate"])), fmt_int(r["misses"]), fmt_int(r["accesses"])] for r in sorted(a, key=lambda r: (int(r["n"]), r["pattern"]))]
    add_table(story, ["N", "Order", "Tile", "Miss rate", "Misses", "Accesses"], rows, [0.55*inch, .8*inch, .55*inch, .85*inch, 1.0*inch, 1.05*inch])
    figure(story, "miss_rate_vs_n", "Figure 6.1. Baseline 32 KiB, 64-byte line, 8-way LRU miss rate by N. Every point comes from cache_exp_a.csv.")

    story.extend(section("Experiment A: access order and N", [
        "Naive i-j-k walks A across a contiguous row, but walks B down a column with a stride of 4N bytes. With N sufficiently large, adjacent B loads usually touch different cache lines. Reordering to i-k-j makes the inner loop traverse B and C contiguously. Tiling limits the working set to a submatrix and increases reuse before those lines are displaced.",
        "The simulator counts the exact four-event stream in the source: load A, load B, load C, store C for every multiply-accumulate. It deliberately models the prompt's explicit C load/store stream. A compiler can keep an accumulator in a register, so the CPU timing experiment below has a different C traffic pattern."
    ], 2))

    if b:
        by_n = {}
        for row in b:
            n = int(row["n"])
            if n not in by_n or float(row["miss_rate"]) < float(by_n[n]["miss_rate"]):
                by_n[n] = row
        best_rows = [[n, r["tile"], fmt_pct(float(r["miss_rate"])), fmt_int(r["misses"])] for n, r in sorted(by_n.items())]
        story.extend(section("Experiment B: tile-size trade-off", [
            "The curve depends on the measured access stream and cache geometry. A tile that is too small exposes less cross-element reuse; a tile that is too large can make its A, B, and C working set compete for cache capacity. A rough working-set estimate is 3T^2 x 4 bytes for three float32 tiles, before considering associativity, line rounding, other data, and the simulator's repeated C events.",
            "The simple capacity estimate is a guide, not a theorem: mapping multiple rows to the same sets can cause conflict misses before nominal byte capacity is reached. The plotted sweep is the evidence for the tested cases."
        ], 2))
        add_table(story, ["N", "Lowest-miss T", "Miss rate", "Misses"], best_rows, [.75*inch, 1.0*inch, 1.0*inch, 1.15*inch])
        figure(story, "miss_rate_vs_tile", "Figure 6.2. Tiled miss rate versus T, measured from cache_exp_b.csv.")

    if c:
        selected = sorted(c, key=lambda r: (int(r["cache_bytes"]), r["pattern"]))
        table_rows = [[int(r["cache_bytes"]) // 1024, r["pattern"], fmt_pct(float(r["miss_rate"])), fmt_int(r["misses"])] for r in selected]
        story.extend(section("Experiment C: cache capacity", [
            "Increasing capacity can retain more of the three matrices and reduce refetching. The amount of reduction depends on the access order and set mapping; the figure reports the actual values instead of assuming a smooth or monotonic curve across all configurations."
        ], 2))
        add_table(story, ["Cache KiB", "Order", "Miss rate", "Misses"], table_rows, [.9*inch, .8*inch, 1.0*inch, 1.1*inch])
        figure(story, "miss_rate_vs_cache_size", "Figure 6.3. Fixed-N capacity sweep. Cache size, line size and associativity are read from the CSV.")

    if d:
        assoc = [r for r in d if r["experiment"] == "D-associativity"]
        lines = [r for r in d if r["experiment"] == "D-line-size"]
        story.extend(section("Experiment D: associativity and line size", [
            "Associativity changes how many competing blocks can share one set. A direct-mapped cache has one candidate line per set; a fully associative cache allows any block to occupy any line. Longer lines can improve spatial locality when nearby data is used, but they also reduce the number of lines at fixed capacity and can increase false sharing of cache capacity at the line granularity.",
            "The experiment holds total cache capacity constant for each sub-sweep. Results should be read in that context; changing line size also changes the number of sets and the address-index bits."
        ], 2))
        if assoc:
            rows = [[r["pattern"], "Fully" if int(r["ways"]) == int(r["cache_bytes"]) // int(r["line_bytes"]) else r["ways"], fmt_pct(float(r["miss_rate"]))] for r in assoc]
            add_table(story, ["Order", "Ways", "Miss rate"], rows, [1.1*inch, 1.0*inch, 1.0*inch])
            figure(story, "miss_rate_vs_associativity", "Figure 6.4. Associativity comparison at fixed capacity and line size.")
        if lines:
            rows = [[r["pattern"], r["line_bytes"], fmt_pct(float(r["miss_rate"]))] for r in lines]
            add_table(story, ["Order", "Line bytes", "Miss rate"], rows, [1.1*inch, 1.0*inch, 1.0*inch])
            figure(story, "miss_rate_vs_line_size", "Figure 6.5. Line-size comparison at fixed cache capacity.")

    if conflict:
        values = [[r["n"], r["pattern"], fmt_pct(float(r["miss_rate"])), fmt_int(r["misses"])] for r in conflict]
        story.extend(section("Experiment D: power-of-two stride case", [
            "For a row-major float32 matrix, the row stride is 4N bytes. At a power-of-two N, that stride is a regular multiple of cache lines, so repeated column traversals can revisit a limited set pattern. Padding the leading dimension changes the stride-to-set relationship. The quick sweep uses N=128 versus N=132 as a scaled case; the full sweep uses N=512 versus N=520. The measured result, which can vary by access order, is shown below."
        ], 2))
        add_table(story, ["N", "Order", "Miss rate", "Misses"], values, [.65*inch, .9*inch, 1.0*inch, 1.1*inch])
        figure(story, "power2_vs_padded_stride", "Figure 6.6. Power-of-two dimension versus nearby padded leading dimension.")

    if e:
        rows = [[r["pattern"], fmt_int(r["compulsory"]), fmt_int(r["capacity"]), fmt_int(r["conflict"]), fmt_int(r["misses"])] for r in e]
        story.extend(section("Experiment E: the 3 C's", [
            "Compulsory misses are first references to a block. A non-compulsory miss is a capacity miss if the equal-size fully associative LRU shadow also misses, and a conflict miss if that shadow hits. This is the simulator's explicit reference definition for the optional classifier; the taxonomy depends on that reference policy."
        ], 2))
        add_table(story, ["Order", "Compulsory", "Capacity", "Conflict", "Total"], rows, [1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch, .8*inch])
        figure(story, "miss_classification", "Figure 6.7. Classified misses from cache_exp_e.csv.")

    story.extend(section("AMAT: an illustrative translation", [
        "Average memory access time is approximated as hit time + miss rate x miss penalty. This project uses an example 4-cycle hit and 200-cycle additional miss penalty. These are illustrative assumptions, not local measurements. For example, a measured miss rate m maps to 4 + 200m cycles in this simplified calculation; it does not predict a processor's full memory behavior because it omits overlap, multiple cache levels, prefetching and out-of-order execution."
    ], 2))
    if a:
        amat_n = max(int(r["n"]) for r in a)
        selected = [r for r in a if int(r["n"]) == amat_n and r["pattern"] in ("naive", "tiled")]
        add_table(story, ["N", "Order", "Miss rate", "Illustrative AMAT cycles"],
                  [[amat_n, r["pattern"], fmt_pct(float(r["miss_rate"])), f"{float(r['amat_cycles_illustrative']):.2f}"] for r in selected],
                  [.55*inch, .8*inch, .9*inch, 1.55*inch])

    story.append(heading("7. Real CPU benchmark", 1))
    story.append(P("The C++ benchmark allocates row-major float32 matrices, warms each implementation, checks its result against naive multiplication, and reports median wall-clock time and 2N^3/time GFLOP/s. The CPU code uses a register accumulator in naive i-j-k, while ikj and tiled update C in the inner loop; therefore the trace simulator and the CPU implementation are related but not identical."))
    if cpu:
        cpu_summary = {}
        for row in cpu:
            n = int(row["n"])
            key = (n, row["algorithm"])
            cpu_summary[key] = max(cpu_summary.get(key, 0.0), float(row["gflops"]))
        rows = []
        for n in sorted({key[0] for key in cpu_summary}):
            rows.append([n] + [f"{cpu_summary.get((n, algo), float('nan')):.3f}" if (n, algo) in cpu_summary else "-" for algo in ("naive", "ikj", "tiled")])
        add_table(story, ["N", "Naive GFLOP/s", "ikj GFLOP/s", "Best tiled GFLOP/s"], rows, [.65*inch, 1.15*inch, 1.15*inch, 1.45*inch])
        figure(story, "cpu_gflops_vs_n", "Figure 7.1. Median measured CPU throughput. For tiled, the plotted value is the fastest measured tile size at each N.")
        common = sorted(set(int(r["n"]) for r in a) & set(int(r["n"]) for r in cpu))
        if common:
            n = common[-1]
            sim_rows = [r for r in a if int(r["n"]) == n]
            cpu_rows = [r for r in cpu if int(r["n"]) == n]
            sim_tiled = next((float(r["miss_rate"]) for r in sim_rows if r["pattern"] == "tiled"), None)
            sim_naive = next((float(r["miss_rate"]) for r in sim_rows if r["pattern"] == "naive"), None)
            cpu_best = {algo: max(float(r["gflops"]) for r in cpu_rows if r["algorithm"] == algo) for algo in ("naive", "ikj", "tiled") if any(r["algorithm"] == algo for r in cpu_rows)}
            comparison = ""
            if "naive" in cpu_best and "tiled" in cpu_best:
                relation = "higher" if cpu_best["tiled"] > cpu_best["naive"] else "lower"
                comparison = f" The best tiled CPU run was {relation} than naive at this N; ikj was "
                if "ikj" in cpu_best:
                    comparison += "the highest-throughput order." if cpu_best["ikj"] >= max(cpu_best.values()) else "also measured."
            story.append(P(f"At the largest shared N={n}, simulator miss rates were {fmt_pct(sim_naive)} for naive and {fmt_pct(sim_tiled)} for tiled. The highest CPU throughput at the same N was " + ", ".join(f"{algo} {value:.3f} GFLOP/s" for algo, value in cpu_best.items()) + "." + comparison + " These two measurements do not imply a direct conversion from cache misses to CPU time."))
    else:
        story.append(P("CPU result CSV is missing; run python python/run_cpu_bench.py."))
    cpu_name = cpu[0].get("cpu_name", "not recorded") if cpu else "not recorded"
    story.append(P(f"Host: {platform.platform()}. Processor string recorded by Python: {cpu_name}. Compiler flags: g++ -std=c++17 -O3 -Wall -Wextra -pedantic, without -ffast-math; ordinary -O3 compiler vectorization remains enabled. Compiler: {compiler_version()}. The C++ benchmark uses std::chrono::steady_clock."))
    story.extend(section("Why hardware time can disagree with simulated miss rate", [
        "Real CPUs prefetch regular streams, execute independent work out of order, use SIMD, and have more than one cache level. TLB reach and page walks also affect matrix traversals. A lower L1-style miss rate can help, but it does not determine runtime by itself. Compiler vectorization, instruction count, clock scaling, thermal state, allocator placement, and OS scheduling add further effects.",
        "This is why the report compares both measurements and explains their different models instead of treating simulator miss count as a CPU benchmark."
    ], 2))


def build_story() -> list:
    story: list = []
    story.extend([Spacer(1, .8*inch), P("Why Tiling Works", "CoverTitle"), P("Cache Simulation and GPU Matrix Multiplication", "CoverSub"),
                  Spacer(1, .2*inch), P("A reproducible teaching project in computer architecture and GPU performance", "CoverSub"),
                  Spacer(1, .35*inch), P("Report generated from local experiment outputs", "CoverSub"),
                  Spacer(1, .2*inch), P("Audience: a computer science student who knows programming and basic machine learning, and is new to computer architecture and CUDA.", "CoverSub"),
                  Spacer(1, 1.3*inch), P("Research question", "H2x"),
                  P("Why is tiled matrix multiplication faster than the naive version? We answer this first with explicit cache-line traffic, then with CPU timings, and finally with a CUDA path that reports real GPU data when run on a CUDA-capable system."), PageBreak()])

    story.append(heading("Contents and roadmap", 1))
    for item in [
        "1. Introduction", "2. Background concepts", "3. Simulator design and implementation", "4. Validation",
        "5. Experimental setup", "6. Simulator results", "7. Real CPU benchmark", "8. CUDA kernels and results",
        "9. Connecting cache reuse and GPU shared memory", "10. Limitations and threats to validity", "11. Conclusions and future work",
        "Appendix A. Glossary", "Appendix B. Reproduction", "Appendix C. Interview questions and model answers", "Appendix D. References"
    ]:
        story.append(P(item))
    story.append(PageBreak())

    story.append(heading("1. Introduction", 1))
    story.append(P("Matrix multiplication is a central operation in scientific computing and machine learning. Dense layers, attention projections, convolutions lowered to matrix products, and many numerical workloads perform large numbers of multiply-accumulate operations. The arithmetic is simple; arranging data movement so the arithmetic units stay busy is the hard part."))
    story.append(P("A naive implementation follows the textbook formula. A tiled implementation divides matrices into smaller blocks and reuses those blocks while they are nearby in the memory hierarchy. This report asks why that helps, and where a CPU cache model predicts the same effect as a GPU shared-memory kernel."))
    story.append(P("The project has three evidence layers: a trace-driven single-level cache simulator, a real C++ CPU benchmark, and CUDA source plus a benchmark driver for a CUDA host. Each layer measures a different system. The simulator counts modeled cache events; the CPU program measures elapsed time; the GPU program uses CUDA events and compares against cuBLAS."))
    story.append(P("The report begins with locality and cache organization, then derives matrix access patterns, explains the simulator and its validation, analyzes measured cache and CPU results, and closes by connecting CPU cache reuse to GPU shared-memory staging."))

    story.append(heading("2. Background concepts", 1))
    story.extend(section("2.1 Memory hierarchy, latency and bandwidth", [
        "A processor has small storage close to its execution units and larger storage farther away. Registers hold values being used by instructions. Caches keep copies of recently or nearby used memory lines. DRAM holds the large working data set. Moving data from farther away generally costs more latency and consumes more shared bandwidth.",
        "Latency is the time from requesting data until it can be used. Bandwidth is the amount of data transferred per unit time once transfers are in flight. A program can be latency-bound when it waits on dependent loads, or bandwidth-bound when it requests data faster than the memory system can supply it. Reusing loaded data improves both: it avoids requests and reduces traffic.",
        "Caches exist because most programs exhibit locality. They automatically retain recently accessed lines and fetch a full line around a requested byte. Software tiling applies the same idea explicitly by scheduling reuse while a chosen block is close to the compute units."
    ]))
    figure(story, "memory_hierarchy", "Figure 2.1. Conceptual hierarchy. The diagram is explanatory, not a measured latency scale.")
    story.extend(section("2.2 Temporal and spatial locality", [
        "Temporal locality means that if a value was used recently, it may be used again soon. Spatial locality means that nearby addresses may be used close together in time. A cache line exploits spatial locality by fetching adjacent bytes together.",
        "For example, with 64-byte lines and float32 values, a line holds 64/4 = 16 matrix elements. A row-wise loop can use most of those 16 values after the first miss. A column-wise loop with a stride larger than a line may waste most fetched bytes."
    ]))
    story.extend(section("2.3 Cache organization and address fields", [
        "A cache is described by total capacity C, line size L, and associativity W. The number of sets is S = C/(L x W). A direct-mapped cache has W=1, a set-associative cache has several ways per set, and a fully associative cache has one set containing every line.",
        "For power-of-two L and S, an address is split into an offset selecting a byte within a line, an index selecting a set, and a tag identifying which memory line is stored there. Offset bits = log2(L); index bits = log2(S); remaining high bits form the tag. The set index is extracted with a mask; no division is needed in the hot path."
    ]))
    figure(story, "address_decomposition", "Figure 2.2. Worked 32-bit address decomposition for a 32 KiB, 64-byte, 8-way cache.")
    story.append(P("Numerically: 32 KiB / (64 bytes x 8 ways) = 64 sets. Offset width is 6 bits and index width is 6 bits. Address 0x1234 has offset 0x34 = 52; its index is (0x1234 >> 6) & 63 = 8; its tag is 0x1234 >> 12 = 1. The fields are therefore tag 1, set 8, offset 52."))
    story.extend(section("2.4 Replacement and write policy", [
        "When all ways in a set are occupied, a replacement rule chooses a victim. LRU replaces the line not used for the longest time. FIFO replaces the line that has been resident the longest, regardless of later hits. LRU often tracks temporal locality better, while FIFO is simpler to describe and can behave differently for cyclic patterns.",
        "Write-through propagates each store to the next level immediately. Write-back marks a modified line dirty and writes the entire line only when it is evicted. Write-allocate brings a missed store's line into the cache before modifying it. This simulator uses write-back and write-allocate for both replacement policies and counts write-backs on dirty evictions."
    ]))
    story.extend(section("2.5 The 3 C's of misses", [
        "A compulsory miss is the first reference to a block. A capacity miss occurs when the working set cannot fit even in a fully associative cache of equal line capacity. A conflict miss occurs when the set mapping forces eviction even though another placement could have retained the block.",
        "The optional classifier keeps a fully associative LRU shadow cache with the same number of lines. It records previously seen block addresses. A main-cache miss on a never-seen block is compulsory; otherwise, a shadow miss is capacity; a shadow hit is conflict. This definition gives a clear reference model, though a different replacement policy may change the classification."
    ]))
    story.extend(section("2.6 Row-major matrices and loop order", [
        "In row-major layout, element A[i][j] is stored at base + (iN+j) x sizeof(float). Columns of a row are adjacent; successive rows are N elements apart. The stride of a column access is 4N bytes for float32.",
        "The textbook i-j-k loop computes one C[i][j] at a time. A[i][k] walks a row contiguously, but B[k][j] walks a column with stride 4N bytes. If that stride spans separate lines and the matrix is larger than cache, many bytes brought in with each B line are not used before eviction.",
        "Reordering to i-k-j makes j the innermost loop. B[k][j] and C[i][j] are now contiguous as j changes. The current A[i][k] value is reused across the row. Tiling adds bounded row, column, and K blocks so an A block and B block can be reused across output elements before moving to the next region."
    ]))
    story.append(P("The simulator's tiled order is ii, kk, jj, then i, k, j. Within one K and column tile, A[i][k] is held conceptually across the contiguous j tile, B[k][j] is streamed by row, and C[i][j] lines are revisited while the working region remains resident. The code uses clipped loop bounds, so edge tiles work for dimensions not divisible by T."))
    story.extend(section("2.7 A simplified traffic derivation and tile choice", [
        "Let N be the matrix dimension, T the tile width, L the cache-line size in bytes, and E=L/4 the float32 values per line. Every multiply-accumulate performs one arithmetic product and addition. The simulator emits four logical accesses per multiply-accumulate, so its event count is exactly 4N^3 for all three loop orders. This is an access-model count, not a claim that each event misses in DRAM.",
        "In a simplified cold-memory traffic model with N divisible by T, a tiled algorithm loads about N^3/T elements from A and N^3/T from B because each staged value is reused across T outputs. Initializing and writing C adds about 2N^2 elements. The total is roughly 2N^3/T + 2N^2 float elements, or that quantity divided by E for an ideal line count. This omits edge waste, set conflicts, replacement, write allocation, and the prompt's repeated explicit C load/store events.",
        "For naive i-j-k, an idealized contiguous A stream can use E adjacent values per line, but B's column stride can make its N^3 loads approach N^3 line fills when the stride exceeds a line and reuse does not survive in cache. A more precise miss count depends on N, line alignment, cache mapping, and replacement, which is why the project simulates addresses instead of treating this simplification as measured truth.",
        "Three T x T float tiles require roughly 3T^2 x 4 bytes. A first sizing estimate is to keep that below the target cache capacity, then test values around it. Real usable capacity is smaller due to associativity, line effects, other live data, and imperfect alignment. The experiment sweeps T instead of claiming one universal optimum."
    ]))
    story.extend(section("2.8 GPU execution basics", [
        "A CUDA program launches a grid of thread blocks. A block contains threads that can cooperate through shared memory and barriers. On NVIDIA hardware, threads execute in groups called warps, commonly 32 threads. A multiprocessor schedules resident warps; available registers and shared memory limit how many blocks can remain resident. That limit is part of occupancy, the fraction of hardware warp capacity occupied by active warps.",
        "Global memory is large device memory. Shared memory is an explicitly managed, on-chip address space shared by one block. Registers are private to a thread. Global loads are most efficient when lanes in a warp request adjacent addresses, allowing memory transactions to coalesce. Shared memory is divided into banks; some access patterns make lanes contend for a bank, though this baseline project does not add a padded-bank-conflict variant.",
        "__syncthreads() is a block-wide barrier. Every participating thread must reach it along a compatible control path. In the tiled kernel, one barrier makes cooperative loads visible before multiply-accumulate; a second ensures all reads from the current shared tiles finish before they are overwritten by the next K tile."
    ]))
    figure(story, "gpu_coalescing", "Figure 2.3. Address mapping for four neighboring lanes; offsets are schematic float32 byte offsets.")
    figure(story, "gpu_tiled_kernel", "Figure 2.4. One block loads two tiles, synchronizes, reuses them, and accumulates one output tile.")
    story.extend(section("2.9 The tiled GPU kernel step by step", [
        "Each block owns a T x T output region. Thread (ty, tx) loads A[row, k0+tx] into shared tile A and B[k0+ty, col] into shared tile B, using zero for out-of-bounds elements. After a barrier, the block loops over the shared K dimension. Each A value is reused across T output columns and each B value across T output rows. The second barrier protects the next tile load. At the end, valid threads write one C element.",
        "The naive GPU kernel assigns one thread to each output element. Its neighboring x threads use neighboring columns of B for a fixed k, which is coalesced. They also request the same A[row,k] value, which hardware caches or broadcasts efficiently. In this mapping B is not the deliberately uncoalesced operand; the main naive-kernel costs include repeated global loads across output threads and the absence of explicit block-level reuse."
    ]))

    story.append(heading("3. Simulator design and implementation", 1))
    story.append(P("The simulator uses C++17. It validates power-of-two cache capacity, line size, associativity and set count, then derives offset and index masks from bit widths. Cache lines live in a flat vector indexed by set and way. Each line stores tag, valid, dirty and a timestamp. The hot path scans only the selected set's ways and performs no per-access allocation."))
    story.append(P("For LRU, a hit refreshes its timestamp; for FIFO, a hit leaves insertion time unchanged. On a miss, an invalid way is preferred, otherwise the oldest timestamp is selected. A store marks the filled or hit line dirty. A dirty victim increments the write-back count. Overall direct cache work is O(W) per access with the implemented way scan and O(C/L) storage."))
    story.append(P("The optional classifier uses a seen-block hash set plus a fully associative equal-line-count LRU shadow map. It adds memory and hash work only when enabled. This is intentionally separate from the default fast path. Matrix addresses are computed on demand from three aligned distinct base regions; no trace file is generated for matrix experiments."))
    story.append(P("The CLI accepts matrix patterns or a text trace. A trace line contains R or W followed by a decimal or 0x hexadecimal byte address. JSON output is used by the Python experiment runner; human and CSV modes are also available. The CPU benchmark is a separate C++ executable with correctness checking, warm-up, repeat timings and median aggregation."))
    story.append(P("In the cache simulator, naive uses i-j-k; ikj uses i-k-j; tiled uses ii-kk-jj-i-k-j. The tiled loop order gives contiguous B/C inner access and reuses A across the tile's columns. The implementation favors an auditable access stream over trace compression; it can process the required high event counts without storing a huge trace, though experiment suites multiply simulation work."))
    performance = read_csv("performance_500m.csv")
    if performance:
        row = performance[0]
        story.append(P(f"Measured throughput check: the simulator processed {fmt_int(row['accesses'])} generated matrix access events for N={row['n']} in {float(row['elapsed_seconds']):.2f} seconds on this host. This run used the ikj generator and the baseline 32 KiB, 64-byte, 8-way LRU cache; the elapsed time is a local measurement, not a cross-machine guarantee."))

    story.append(heading("4. Validation", 1))
    story.append(P("Validation has four complementary parts: a hand-computed set mapping example, analytical access streams, C++ unit tests, and an independent Python reference. The test commands are reproducible with make test."))
    validation = read_csv("validation_results.csv")
    if validation:
        rows = [[r["case"], r["accesses"], r["hits"], r["misses"], r["evictions"], r["write_backs"]] for r in validation]
        add_table(story, ["Test case", "Accesses", "Hits", "Misses", "Evictions", "Write-backs"], rows,
                  [1.35*inch, .7*inch, .55*inch, .65*inch, .75*inch, .85*inch])
    story.append(P("Hand-worked example: four-set direct-mapped cache with 16-byte lines. The sequence is load 0, load 16, load 0, store 64, load 64, load 0. Blocks 0 and 16 map to sets 0 and 1; block 64 maps to set 0. The third reference hits. Storing 64 evicts block 0, the next load of 64 hits, and the final load of 0 misses and writes back dirty block 64. Expected total: 6 accesses, 2 hits, 4 misses, 2 evictions and 1 write-back. The simulator unit test checks these counts."))
    story.append(P("Analytical sanity checks: the test scans 80 float32 values through 64-byte lines, so each line holds 16 values and the observed 5 misses / 80 accesses is 1/16. A repeated working set smaller than the cache misses during warm-up and then hits when it maps without conflict. Cycling over five lines in a four-line fully associative LRU cache misses on all accesses because the next required line has already been evicted."))
    random_tests = read_csv("validation_random_crosscheck.csv")
    if random_tests:
        total = sum(int(r["accesses"]) for r in random_tests)
        story.append(P(f"The independently coded Python model matched the C++ simulator exactly on {len(random_tests)} deterministic randomized traces totaling {total:,} accesses. The tests cover LRU and FIFO, loads and stores, and compare access, hit, miss, eviction and write-back counts. Every classified miss was also checked to belong to exactly one of the three categories."))
    else:
        story.append(P("Randomized cross-check CSV is missing. Run make test to regenerate it."))
    story.append(P("The classifier's validation includes compulsory, capacity and conflict accounting. For a cyclic stream that exceeds capacity, every miss is required to be counted; a fully fitting repeated working set is required to have only warm-up misses."))

    story.append(heading("5. Experimental setup", 1))
    metadata = read_json("experiment_metadata.json", {})
    base = metadata.get("cache_baseline", {"cache_bytes": 32768, "line_bytes": 64, "ways": 8, "policy": "lru"})
    story.append(P(f"Cache baseline: {int(base['cache_bytes']) // 1024} KiB, {base['line_bytes']}-byte lines, {base['ways']}-way, {base['policy'].upper()} replacement. Matrices are float32, row-major, and use separate aligned address regions. The baseline is a modeling choice similar in scale to an L1 data cache; it is not a claim that every CPU has this exact organization."))
    story.append(P(f"Operating system string: {platform.platform()}. Python: {platform.python_version()}. Compiler: {compiler_version()}. C++ build flags: -std=c++17 -O3 -Wall -Wextra -pedantic. No -ffast-math flag is used. The host processor string is stored in results/cpu_results.csv."))
    story.append(P("Cache experiments log the exact matrix dimension, pattern, tile, cache capacity, line size, ways, replacement policy, access/hit/miss counts, miss rate, evictions, write-backs, optional 3C counts and simulator wall time. The CPU CSV records N, algorithm, tile, median time, GFLOP/s, repeat count and processor string."))
    story.append(P("For the AMAT illustration only, the report uses a 4-cycle hit and a 200-cycle additional miss penalty. These values are assumptions selected to demonstrate the calculation and are not captured by a timer or read from the machine."))

    results_context(story)

    story.append(heading("8. CUDA kernels and results", 1))
    story.append(P("The CUDA source contains a naive global-memory kernel, templated shared-memory tiled kernels for widths 8, 16 and 32, and a cuBLAS SGEMM reference. All CUDA and cuBLAS API calls use error-checking macros. Tiled boundaries use zero fill and output guards, so arbitrary N values are supported."))
    story.append(P("The driver uses deterministic input, cuBLAS as the GPU correctness reference, absolute tolerance 0.01 and relative tolerance 0.001, two warm-up launches, CUDA-event timing, and the median of repeated runs. It records GPU name, CUDA runtime and driver versions, N, kernel, tile, seconds, GFLOP/s and tolerance. For row-major C=A*B, the cuBLAS call computes column-major C^T=B^T*A^T using the same memory buffers in reversed operand order."))
    gpu = read_csv("gpu_results.csv")
    if not gpu:
        pending = Table([[P("RESULTS PENDING - run on a GPU", "Pendingx")],
                         [P("This environment has no nvcc command available, so no GPU timing result is claimed. The CUDA source is documented but has not been compiled or run here. Use notebooks/run_gpu_on_colab.ipynb or run make gpu on a CUDA Toolkit host; the driver writes results/gpu_results.csv. Then run make figures report to rebuild this report.")]], colWidths=[6.5*inch])
        pending.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ORANGE), ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#D39B35")), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
        story.extend([pending, Spacer(1, 10)])
    else:
        story.append(P(f"GPU results CSV is present with {len(gpu)} measured rows. GPU names recorded: {', '.join(sorted({r['gpu_name'] for r in gpu}))}. CUDA runtime versions: {', '.join(sorted({r['cuda_runtime'] for r in gpu}))}; driver versions: {', '.join(sorted({r['cuda_driver'] for r in gpu}))}."))
        figure(story, "gpu_gflops_vs_n", "Figure 8.1. Measured CUDA-event throughput from gpu_results.csv.")
        gpu_rows = [[r["n"], r["algorithm"], r["tile"], f"{float(r['seconds']):.6f}", f"{float(r['gflops']):.3f}", r["gpu_name"]] for r in gpu]
        add_table(story, ["N", "Kernel", "T", "Seconds", "GFLOP/s", "GPU"], gpu_rows,
                  [.5*inch, .75*inch, .35*inch, .75*inch, .7*inch, 2.0*inch])
    story.extend(section("Nsight Compute", [
        "If ncu is installed, python/profile_ncu.sh requests the basic metric set for the naive and tiled kernels at N=512. Nsight Compute can report memory throughput and transactions, L1/L2 behavior, shared-memory activity and achieved occupancy. Metric availability varies by GPU and tool version; the script saves profiler reports rather than copying values into this PDF. No profiler value is claimed unless generated by a real run."
    ], 2))

    story.append(heading("9. Connecting the two levels", 1))
    story.append(P("The CPU cache and GPU shared-memory stories share a principle: load a useful region, perform several operations with it, and move on after reuse is exhausted. A cache does this automatically based on line addresses and replacement. A CUDA block stages known tiles explicitly and synchronizes threads around their use."))
    story.append(P("For the matrix product, an A element can contribute to several output columns, and a B element can contribute to several output rows. A tile captures this reuse. Row-wise access makes neighboring data available to adjacent work; less redundant traffic leaves more bandwidth for useful values."))
    story.append(P("The analogy has limits. CPU caches are coherent with the CPU's normal load/store path and are managed mostly in hardware. Shared memory is an explicitly addressed block-local scratchpad. CUDA execution has warps, block barriers, occupancy limits, and global-memory transaction rules. A GPU kernel also has many more concurrent threads, and the compiler and hardware schedule work differently. Shared memory is not simply a manually programmed CPU cache."))
    story.append(P("The naive GPU mapping here already coalesces B across neighboring columns; the benefit of tiling is therefore broader than fixing one bad coalescing pattern. It reduces repeated global fetches by using each shared A and B value across multiple output elements. The actual speedup depends on GPU generation, occupancy, launch overhead, memory behavior and compiler code generation, so it must be measured on the target GPU."))

    story.append(heading("10. Limitations and threats to validity", 1))
    for text in [
        "The cache simulator models one set-associative cache only. It has no L2/LLC hierarchy, coherence, prefetcher, TLB, nonblocking miss machinery, or out-of-order execution.",
        "Each multiply-accumulate emits a load A, load B, load C, and store C by design. A real CPU compiler can keep C values in registers and combine operations; this model is explicit and pedagogical rather than a compiler trace.",
        "The access generator is single-threaded and models one address stream. Real CPU and GPU workloads interleave requests, overlap misses, and contend for resources.",
        "The optional 3C shadow model uses fully associative LRU of equal line count. Another reference replacement rule can assign a different label to a miss.",
        "The illustrative AMAT values are assumptions. The real CPU benchmark is affected by thermal state, clocks, OS activity, compiler version, vectorization, alignment and allocator behavior.",
        "The CUDA benchmark has not been compiled or run unless gpu_results.csv is present. Kernel timing, tolerance behavior, compiler output and profiler metrics need confirmation on actual CUDA hardware.",
        "The hand-written CUDA kernels are educational examples. cuBLAS uses architecture-specific tiling, pipelining, vectorization and other optimizations, so its result is a highly tuned reference, not a like-for-like implementation.",
    ]:
        story.append(P(text))

    story.append(heading("11. Conclusions and future work", 1))
    story.append(P("Tiling works by changing when and how often data is moved. Loop reordering improves contiguous access; blocking limits the active region and reuses values across output work. The simulator makes line behavior visible, and the CPU benchmark shows how real timing also depends on instruction execution and the broader memory system."))
    story.append(P("The project's measured conclusions are deliberately data-dependent. The report names the measured lowest-miss tile, displays all recorded sweep points, and compares simulator miss rates with CPU throughput at shared matrix sizes. A GPU run is left explicitly pending until the CUDA driver writes its CSV."))
    story.append(P("Useful next steps include running the full cache sweep, collecting GPU results on Colab or a local CUDA host, saving Nsight Compute reports, varying the leading dimension and tile shape, and examining compiler-generated assembly. Further cache levels or coherence are outside this project's scope."))

    story.append(PageBreak())
    story.append(heading("Appendix A. Glossary", 1))
    glossary = [
        ("AMAT", "Average memory access time: a simplified average of hit time and miss penalty contribution."),
        ("Bandwidth", "Data transferred per unit time."),
        ("Cache line", "The fixed-size aligned block moved between cache and the next memory level."),
        ("Coalescing", "Combining lane memory requests that touch nearby addresses into fewer transactions."),
        ("Dirty line", "A cached line modified since it was loaded and therefore requiring write-back on eviction."),
        ("Eviction", "Removal of a line to make room for another line."),
        ("GFLOP/s", "Billions of floating-point operations per second."),
        ("Latency", "Delay between a request and the availability of its result."),
        ("Locality", "Reuse in time or nearby addresses."),
        ("Occupancy", "Active warps relative to a multiprocessor's supported warp capacity."),
        ("Set associativity", "Number of candidate cache lines, or ways, for each set index."),
        ("Shared memory", "An explicitly managed, block-local on-chip storage space in CUDA."),
        ("Stride", "Address distance between successive elements in a loop."),
        ("Tile", "A block of matrix elements loaded and reused as a unit."),
        ("Write allocate", "Policy that places a store-missed line into cache before modifying it."),
        ("Write-back", "Policy that delays writing modified data until line eviction."),
    ]
    add_table(story, ["Term", "Definition"], [[term, definition] for term, definition in glossary], [1.25*inch, 5.25*inch])

    story.append(heading("Appendix B. Reproduction", 1))
    commands = [
        "1. Install g++ with C++17 support, Python 3.10 or newer, and the packages in requirements.txt.",
        "2. Run make build to compile the cache simulator and CPU benchmark with -O3.",
        "3. Run make test to check the hand examples, analytical patterns and randomized Python/C++ cross-checks.",
        "4. Run make quick for a shorter measured cache and CPU sweep, generated figures and a pending-GPU PDF.",
        "5. Run make all for the full N=64,128,256,512 cache sweep, the N=512/520 stride comparison, CPU benchmark, figures and report.",
        "6. On a CUDA Toolkit machine, run make gpu. This builds the CUDA driver, runs the GPU sweep and rebuilds plots and PDF.",
        "7. Alternatively, open notebooks/run_gpu_on_colab.ipynb, set your repository URL, and run all cells on a Colab GPU runtime.",
        "8. After adding results/gpu_results.csv from a GPU run, run make figures report to regenerate the GPU figures and PDF.",
        "9. Run make clean only when you want to remove generated binaries, CSVs, figures and the generated PDF.",
    ]
    for command in commands:
        story.append(P(command))
    story.append(P("The simulator CLI can also read a text trace with build/cache_sim --trace PATH. Run build/cache_sim --help for all cache, policy, classification and output-format options. The report source and generation logic live in python/build_report.py; measured data are read from results/*.csv."))

    story.append(heading("Appendix C. Questions and model answers", 1))
    qa = [
        ("1. Why is a row-wise scan usually more cache-friendly than a column-wise scan in row-major storage?", "A row's elements are adjacent and use the rest of each fetched line; column elements are separated by the row stride."),
        ("2. How many float32 elements fit in a 64-byte line?", "64/4 = 16 elements."),
        ("3. What does a cache set index select?", "The set containing the candidate ways where a line may be stored."),
        ("4. What decides whether an address hits after the set is selected?", "A valid line in that set has a matching tag."),
        ("5. How do LRU and FIFO differ?", "LRU refreshes recency on a hit; FIFO preserves insertion order."),
        ("6. What does write-back change?", "A dirty line is written to the next level at eviction rather than on every store."),
        ("7. Why does i-k-j improve the inner loop for row-major B?", "The j index changes fastest, so consecutive B values are adjacent."),
        ("8. What is the approximate three-tile working set?", "About 3T^2 float32 values, or 12T^2 bytes, before overheads."),
        ("9. Why can a tile that is too large lose?", "It can exceed useful cache capacity or create set conflicts, reducing reuse."),
        ("10. What is a compulsory miss?", "The first access to a memory block in the measured trace."),
        ("11. What is coalescing?", "Neighboring GPU lanes access nearby addresses that can be served by fewer memory transactions."),
        ("12. Why does a tiled CUDA block need barriers?", "Threads must finish loading before peers consume shared tiles and finish consuming before the next tile overwrites them."),
        ("13. Why can increasing shared-memory usage lower performance?", "It can reduce the number of resident blocks and active warps, lowering occupancy."),
        ("14. Why is cuBLAS faster than a simple teaching kernel?", "It applies hardware-specific optimizations such as advanced tiling, pipelining and tuned instruction selection."),
        ("15. Why does a cache miss-rate improvement not guarantee the same CPU speedup?", "Prefetching, SIMD, execution overlap, deeper caches, TLBs and instruction costs also affect time."),
    ]
    for question, answer in qa:
        story.extend([P(f"<b>{question}</b>"), P(f"{answer}")])

    story.append(heading("Appendix D. References", 1))
    refs = [
        "[1] John L. Hennessy and David A. Patterson, Computer Architecture: A Quantitative Approach. Morgan Kaufmann.",
        "[2] David B. Kirk and Wen-mei W. Hwu, Programming Massively Parallel Processors: A Hands-on Approach. Morgan Kaufmann.",
        "[3] NVIDIA, CUDA C++ Programming Guide. NVIDIA CUDA documentation.",
        "[4] Monica S. Lam, Edward E. Rothberg, and Michael E. Wolf, The Cache Performance and Optimizations of Blocked Algorithms. Proceedings of ASPLOS IV, 1991.",
        "[5] Onur Mutlu, public lectures on computer architecture and memory systems. ETH Zurich / Carnegie Mellon University course materials.",
    ]
    for ref in refs:
        story.append(P(ref))
    story.append(P("Reference list limited to established textbooks, the official CUDA programming guide, and the blocked-algorithm paper specified in the project brief.", "Smallx"))
    return story


def footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = letter
    canvas.setStrokeColor(colors.HexColor("#D9E1E8"))
    canvas.setLineWidth(.5)
    canvas.line(.7*inch, .55*inch, width-.7*inch, .55*inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(.72*inch, .36*inch, "Tilescope | Cache simulation and GPU matrix multiplication")
    canvas.drawRightString(width-.72*inch, .36*inch, f"Page {doc.page}")
    canvas.restoreState()


def main() -> None:
    PDF.parent.mkdir(exist_ok=True)
    doc = BaseDocTemplate(str(PDF), pagesize=letter, rightMargin=.72*inch, leftMargin=.72*inch,
                          topMargin=.68*inch, bottomMargin=.78*inch, title="Why Tiling Works",
                          author="Tilescope project")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=footer)])
    doc.build(build_story())
    if not PDF.exists() or PDF.stat().st_size < 5000 or PDF.read_bytes()[:5] != b"%PDF-":
        raise RuntimeError("Report PDF failed basic file validation")
    print(f"Built {PDF} ({PDF.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
