import argparse
from collections.abc import Sequence


def create_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="rct",
        description="Build and run trustworthy RISC-V numerical-computing experiments.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    create_parser().parse_args(argv)
    return 0
