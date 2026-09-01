import argparse
from collections.abc import Sequence
from pathlib import Path

from rct.benchmark import BenchmarkError, render_experiment, run_benchmark
from rct.disasm import DEFAULT_PRESET, DisassemblyError, disassemble


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rct",
        description="Build and run trustworthy RISC-V numerical-computing experiments.",
    )
    subparsers = parser.add_subparsers(dest="command")
    disasm_parser = subparsers.add_parser(
        "disasm", help="Disassemble one or more benchmark kernels."
    )
    disasm_parser.add_argument(
        "kernels",
        metavar="KERNEL",
        nargs="+",
        help="Kernel aliases in display order: reference, scalar, or auto.",
    )
    disasm_parser.add_argument(
        "--binary",
        type=Path,
        help="Path to the benchmark binary. Overrides --preset.",
    )
    disasm_parser.add_argument(
        "--preset",
        default=DEFAULT_PRESET,
        help=f"CMake build preset used to locate the binary (default: {DEFAULT_PRESET}).",
    )
    disasm_parser.add_argument(
        "--no-source",
        action="store_false",
        dest="include_source",
        help="Show assembly without interleaved source.",
    )
    benchmark_parser = subparsers.add_parser(
        "benchmark", help="Run vector_add_f32 and collect an experiment record."
    )
    benchmark_parser.add_argument(
        "--binary",
        type=Path,
        help="Path to the benchmark binary. Overrides --preset.",
    )
    benchmark_parser.add_argument(
        "--preset",
        default=DEFAULT_PRESET,
        help=f"CMake build preset used to locate the binary (default: {DEFAULT_PRESET}).",
    )
    benchmark_parser.add_argument("--length", help="Vector length passed to the benchmark.")
    benchmark_parser.add_argument("--warmup", help="Warmup iterations passed to the benchmark.")
    benchmark_parser.add_argument(
        "--iterations", help="Measured iterations passed to the benchmark."
    )
    benchmark_parser.add_argument("--seed", help="Input seed passed to the benchmark.")
    benchmark_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write the canonical experiment JSON to standard output.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.command == "disasm":
        try:
            outputs = [
                (
                    kernel,
                    disassemble(
                        kernel, args.binary, args.preset, args.include_source
                    ),
                )
                for kernel in args.kernels
            ]
        except DisassemblyError as error:
            parser.error(str(error))

        if len(outputs) == 1:
            output = outputs[0][1]
        else:
            sections = [
                f"===== {kernel} =====\n{output.strip(chr(10))}"
                for kernel, output in outputs
            ]
            output = "\n\n".join(sections) + "\n"
        print(output, end="")
    elif args.command == "benchmark":
        try:
            experiment = run_benchmark(
                binary=args.binary,
                preset=args.preset,
                length=args.length,
                warmup=args.warmup,
                iterations=args.iterations,
                seed=args.seed,
            )
        except BenchmarkError as error:
            parser.error(str(error))

        if args.json_output:
            print(experiment.to_json(), end="")
        else:
            print(render_experiment(experiment), end="")
    return 0
