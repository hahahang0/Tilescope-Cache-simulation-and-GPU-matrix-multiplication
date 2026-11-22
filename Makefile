PYTHON ?= python

.PHONY: all build test performance experiments gpu-optional figures report quick gpu clean

all: build test performance experiments gpu-optional figures report

build:
	$(PYTHON) python/build.py --target build

test:
	$(PYTHON) python/build.py --target test

performance: build
	$(PYTHON) python/performance_check.py

gpu-optional:
	$(PYTHON) python/run_optional_gpu.py

experiments: build
	$(PYTHON) python/run_experiments.py
	$(PYTHON) python/run_cpu_bench.py

figures:
	$(PYTHON) python/plot_results.py

report: figures
	$(PYTHON) python/build_report.py

quick: build test
	$(PYTHON) python/run_experiments.py --quick
	$(PYTHON) python/run_cpu_bench.py --quick
	$(PYTHON) python/plot_results.py
	$(PYTHON) python/build_report.py

gpu:
	$(PYTHON) python/build_cuda.py
	$(PYTHON) python/run_gpu_bench.py
	$(PYTHON) python/plot_results.py
	$(PYTHON) python/build_report.py

clean:
	$(PYTHON) python/clean.py
