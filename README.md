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
./build/rct_bench --benchmark vector_add_f32
python -m rct --help
```

The portable vector-add benchmark measures reference, scalar, and compiler
auto-vectorized kernels with deterministic inputs and correctness validation.
RVV codegen evidence is collected separately from runtime capability and
compiler-decision evidence.

`python -m rct benchmark --json` writes the versioned experiment record. It
includes the runtime architecture, RISC-V V availability when the Linux kernel
can report it, actual per-kernel compile flags, and GCC's recorded
auto-vectorization diagnostics for the `auto` kernel. Unavailable evidence is
represented explicitly rather than as unsupported hardware or failed
vectorization.

## RVV auto-vectorization experiment

The baseline remains host-portable:

```text
cmake --preset optimized-debug
cmake --build --preset optimized-debug
```

On a native RISC-V GNU build, use a separate build directory and provide the
target ISA deliberately:

```text
cmake --preset optimized-debug-rvv -DRCT_RISCV_ARCH=<explicit-rvv-capable-isa>
cmake --build --preset optimized-debug-rvv
```

`RCT_RISCV_ARCH` becomes `-march=<value>` for the `scalar` and `auto` kernels;
the low-optimization `reference` kernel stays ISA-neutral. Set
`RCT_RISCV_ABI=<abi>` when an explicit ABI is required. The JSON experiment
record captures the resulting commands, compiler diagnostics, and recognized
RVV mnemonic evidence for `scalar` and `auto`; no recognized mnemonic is not a
claim that a function contains no possible RVV instruction.

## Debugging

See [the GDB debugging guide](docs/debugging.md) for source-debug and
optimized-debug workflows.
