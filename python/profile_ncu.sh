#!/usr/bin/env bash
set -euo pipefail
mkdir -p results
ncu --set basic --kernel-name regex:naive_kernel --export results/ncu_naive ./build/gpu_bench --sizes 512 --tile-sizes 16 --repeats 1 --output results/ncu_gpu.csv
ncu --set basic --kernel-name regex:tiled_kernel --export results/ncu_tiled ./build/gpu_bench --sizes 512 --tile-sizes 16 --repeats 1 --output results/ncu_gpu.csv
