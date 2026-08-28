# Debugging RCT

RCT has two intentional debugger workflows. They answer different questions and
must not be confused with one another.

| Build | Question | Optimization policy | Benchmark use |
| --- | --- | --- | --- |
| `source-debug` | What does this source code do? | `-Og`, debug symbols, frame pointers; RCT's per-kernel experiment policy is disabled. | Never use its timings as experiment results. |
| `optimized-debug` | What machine code did the compiler execute? | The normal reference/scalar/auto policy is preserved with debug symbols. | Inspectable, but still not a replacement for a controlled Release measurement. |
| Release | What performance do we actually get? | Normal experiment policy. | Use for experiment measurements. |

GDB is optional. Normal CMake builds, tests, and benchmark execution do not
require GDB or link against it.

## Build configurations

### Source debug

```text
cmake --preset source-debug
cmake --build --preset source-debug
ctest --test-dir build/source-debug --output-on-failure
```

`source-debug` sets `RCT_SOURCE_DEBUG=ON`. With GCC or Clang it adds `-Og`,
`-g3`, and `-fno-omit-frame-pointer`, and does **not** apply the per-source
`-O1`/`-O3` and vectorization options used by the experiment. This makes local
variables, stepping, and stacks substantially more useful. Its benchmark
numbers are not valid RCT measurements.

### Optimized debug

```text
cmake --preset optimized-debug
cmake --build --preset optimized-debug
ctest --test-dir build/optimized-debug --output-on-failure
```

`optimized-debug` uses `RelWithDebInfo` and leaves `RCT_SOURCE_DEBUG=OFF`.
The current CMake policy remains intentional:

- `rct_vector_add_f32_reference`: lower optimization and vectorization disabled;
- `rct_vector_add_f32_scalar`: `-O3` and vectorization disabled;
- `rct_vector_add_f32_auto`: `-O3` with auto-vectorization enabled.

Debug symbols permit source/assembly correlation, while optimized-out
variables, reordered lines, and inlining remain expected observations.

### Release

```text
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/rct_vector_add_bench --length 8 --warmup 1 --iterations 2
```

Release keeps `RCT_SOURCE_DEBUG=OFF` by default, so its experiment semantics
are unchanged.

## Source-debug walkthrough

Use a deliberately small workload:

```text
gdb --tui -x tools/gdb/rct.py --args \
  build/source-debug/rct_vector_add_bench \
  --length 8 --warmup 1 --iterations 2
```

The extension is loaded explicitly with `-x`; RCT does not use a repository
`.gdbinit` or ask users to weaken GDB safe-path protections. From an existing
GDB session, load it with `source tools/gdb/rct.py`.

### Start and orchestration

```text
(gdb) break main
(gdb) run
(gdb) next
(gdb) info locals
(gdb) rct-break-pipeline
(gdb) continue
```

The second stop is `rct_run_vector_add_f32_benchmark`. Its `config` argument
is the actual `rct_vector_add_f32_benchmark_config` pointer used by the
benchmark:

```text
(gdb) print config->length
(gdb) print config->warmup_iterations
(gdb) print config->measured_iterations
(gdb) print config->seed
(gdb) rct-show-config
```

`rct-show-config` is intentionally available only while the stack contains
`rct_run_vector_add_f32_benchmark`; it reads the real C value through GDB's
embedded Python API rather than parsing textual `print` output.

### Inputs and kernels

Continue to the configured breakpoint in `rct_fill_vector_add_f32_inputs`:

```text
(gdb) continue
(gdb) info args
(gdb) next
(gdb) info locals
(gdb) x/8fw lhs
(gdb) x/8fw rhs
```

Step through at least one loop body before inspecting the arrays; the input
function fills `lhs` and `rhs` deterministically from `seed`.

Continue to `rct_vector_add_f32_scalar`:

```text
(gdb) continue
(gdb) info args
(gdb) print length
(gdb) next
(gdb) info locals
(gdb) x/8fw lhs
(gdb) x/8fw rhs
(gdb) x/8fw output
```

After stepping through the unrolled loop, inspect `index` and `output` again
to see the stores caused by the current scalar kernel.

The next configured validation stop is `rct_validate_f32`:

```text
(gdb) continue
(gdb) info args
(gdb) x/8fw actual
(gdb) x/8fw expected
(gdb) next
(gdb) info locals
```

This shows the output/reference buffers used by the current correctness gate.

### Navigate the stack

The same session can move between the benchmark orchestration and its callees:

```text
(gdb) backtrace
(gdb) frame 0
(gdb) up
(gdb) down
(gdb) finish
(gdb) continue
```

## Optimized-debug assembly inspection

Build optimized debug, then launch the same small workload:

```text
gdb --tui --args \
  build/optimized-debug/rct_vector_add_bench \
  --length 8 --warmup 1 --iterations 2
```

Inspect source and generated instructions together:

```text
(gdb) disassemble /s rct_vector_add_f32_scalar
(gdb) disassemble /s rct_vector_add_f32_auto
(gdb) layout asm
(gdb) layout regs
(gdb) x/i $pc
```

This build answers what the compiler actually generated. Do not expect it to
step like source debug: optimized code may reorder instructions, inline calls,
or remove locals. On RISC-V hardware, this is the workflow that will later
show whether vector instructions were emitted.

For a noninteractive code view, use the focused CLI:

```text
rct disasm scalar
rct disasm auto
```

`rct disasm` defaults to the `optimized-debug` build and interleaves source
with assembly; add `--no-source` for assembly only. It prefers `llvm-objdump`
and falls back to GNU `objdump`. Raw full-binary disassembly remains available
with `objdump -dS build/optimized-debug/rct_vector_add_bench`.

## RCT GDB commands

`tools/gdb/rct.py` runs inside GDB's embedded Python interpreter and has no
external dependencies.

```text
(gdb) rct-help
(gdb) rct-break-pipeline
(gdb) rct-show-config
```

- `rct-help` lists the available RCT commands.
- `rct-break-pipeline` creates and reports breakpoints for the current
  vector-add entry point, orchestration, deterministic input generation,
  scalar kernel, and validation. Missing symbols are reported explicitly.
- `rct-show-config` prints the active benchmark configuration when stopped in
  the benchmark orchestration call stack.

Vanilla GDB remains fully usable without this script.

## Future directions

The Python extension is intentionally small. Repeated real debugging needs may
later justify commands for RVV `vl`/`vtype` and vector-register inspection, or
for comparing source and generated code across reference, scalar, auto, and
explicit-RVV kernels. Those are hypotheses, not current features.

Remote RISC-V debugging is a separate task. The expected future path is:

```text
developer laptop → cross-GDB → SSH tunnel → gdbserver → Orange Pi RV2 RCT process
```

RCT does not yet automate SSH, `gdbserver`, remote protocol setup, QEMU,
OpenOCD, or JTAG.
