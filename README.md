# RISC-V Compute Toolkit

RISC-V Compute Toolkit is a small experiment system for trustworthy numerical-computing measurements on the Orange Pi RV2.

Initially it focuses exclusively on deterministic `float32` vector addition. It will compare reference C, optimized scalar C, compiler auto-vectorized C, and explicit RISC-V Vector intrinsics; validate every result; capture target and build environments; and produce JSON results plus a Markdown report.

## Requirements

- CMake 3.20 or newer
- A C11 compiler
- Python 3.11 or newer

## Bootstrap commands

```text
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
python -m unittest discover
./build/rct_vector_add_bench
python -m rct --help
```

The portable vector-add benchmark measures reference, scalar, and compiler
auto-vectorized kernels with deterministic inputs and correctness validation.
RVV execution, run artifacts, and reports remain later Phase 1 steps.

## Debugging

See [the GDB debugging guide](docs/debugging.md) for source-debug and
optimized-debug workflows.
