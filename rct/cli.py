import argparse
from collections.abc import Sequence
from pathlib import Path

from rct.disasm import DEFAULT_PRESET, DisassemblyError, disassemble


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rct",
        description="Build and run trustworthy RISC-V numerical-computing experiments.",
    )
    subparsers = parser.add_subparsers(dest="command")
    disasm_parser = subparsers.add_parser(
        "disasm", help="Disassemble one benchmark kernel."
    )
    disasm_parser.add_argument(
        "kernel", metavar="KERNEL", help="Kernel alias: reference, scalar, or auto."
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.command == "disasm":
        try:
            output = disassemble(
                args.kernel, args.binary, args.preset, args.include_source
            )
        except DisassemblyError as error:
            parser.error(str(error))
        print(output, end="")
    return 0
