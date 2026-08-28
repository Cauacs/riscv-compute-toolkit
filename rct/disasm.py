from pathlib import Path
import shutil
import subprocess


DEFAULT_PRESET = "optimized-debug"
BENCHMARK_BINARY_NAME = "rct_vector_add_bench"
KERNEL_SYMBOLS = {
    "reference": "rct_vector_add_f32_reference",
    "scalar": "rct_vector_add_f32_scalar",
    "auto": "rct_vector_add_f32_auto",
}


class DisassemblyError(RuntimeError):
    """Raised when a requested kernel cannot be disassembled."""


def resolve_kernel_symbol(kernel: str) -> str:
    try:
        return KERNEL_SYMBOLS[kernel]
    except KeyError as error:
        aliases = ", ".join(KERNEL_SYMBOLS)
        raise DisassemblyError(
            f"Unknown kernel alias '{kernel}'. Choose one of: {aliases}."
        ) from error


def resolve_binary_path(binary: Path | None, preset: str) -> Path:
    if binary is not None:
        return binary

    project_root = Path(__file__).resolve().parent.parent
    return project_root / "build" / preset / BENCHMARK_BINARY_NAME


def find_disassembler() -> str:
    for candidate in ("llvm-objdump", "objdump"):
        executable = shutil.which(candidate)
        if executable is not None:
            return executable

    raise DisassemblyError(
        "Could not find a supported disassembler. Install llvm-objdump or objdump."
    )


def build_disassembler_command(
    disassembler: str,
    symbol: str,
    binary: Path,
    include_source: bool,
) -> list[str]:
    command = [disassembler]
    if include_source:
        command.append("--source")

    if Path(disassembler).name.startswith("llvm-objdump"):
        command.append(f"--disassemble-symbols={symbol}")
    else:
        command.append(f"--disassemble={symbol}")

    command.append(str(binary))
    return command


def disassemble(
    kernel: str,
    binary: Path | None,
    preset: str,
    include_source: bool,
) -> str:
    symbol = resolve_kernel_symbol(kernel)
    binary_path = resolve_binary_path(binary, preset)
    if not binary_path.is_file():
        raise DisassemblyError(f"Benchmark binary does not exist: {binary_path}")

    disassembler = find_disassembler()
    command = build_disassembler_command(
        disassembler, symbol, binary_path, include_source
    )
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise DisassemblyError(
            f"Could not run disassembler '{disassembler}': {error}"
        ) from error

    if result.returncode != 0:
        detail = result.stderr.strip()
        message = (
            f"Disassembler '{disassembler}' failed with exit status {result.returncode}."
        )
        if detail:
            message = f"{message} {detail}"
        raise DisassemblyError(message)

    return result.stdout
