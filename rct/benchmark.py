from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import platform
import re
import shlex
import subprocess
from typing import Any

from rct.capabilities import IsaCapabilities, discover_isa_capabilities
from rct.disasm import resolve_binary_path
from rct.vectorization import VectorizationReport, load_vectorization_reports


SCHEMA_VERSION = "1.1"
RESULT_PROTOCOL_HEADER = "rct-benchmark-result-v1"
KERNEL_SOURCES = {
    "reference": "src/kernels/vector_add_reference.c",
    "scalar": "src/kernels/vector_add_scalar.c",
    "auto": "src/kernels/vector_add_auto.c",
}


class BenchmarkError(RuntimeError):
    """Raised when the benchmark process or its result payload is unusable."""


@dataclass(frozen=True)
class BenchmarkMetadata:
    name: str
    length: int
    warmup_iterations: int
    measured_iterations: int
    seed: str


@dataclass(frozen=True)
class Timing:
    min_ns: int
    median_ns: float
    mean_ns: float


@dataclass(frozen=True)
class ImplementationResult:
    validation_passed: bool
    timing: Timing
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation": {"passed": self.validation_passed},
            "timing": asdict(self.timing),
            "sample_count": self.sample_count,
        }


@dataclass(frozen=True)
class CompilerMetadata:
    name: str | None
    version: str | None
    path: str | None


@dataclass(frozen=True)
class BuildMetadata:
    preset: str | None
    kernel_compile_flags: dict[str, list[str]] | None
    vectorization: dict[str, VectorizationReport] | None = None

@dataclass(frozen=True)
class Experiment:
    benchmark: BenchmarkMetadata
    environment_architecture: str | None
    compiler: CompilerMetadata | None
    build: BuildMetadata
    implementations: dict[str, ImplementationResult]
    environment_isa: IsaCapabilities = field(
        default_factory=lambda: IsaCapabilities(vector=None)
    )
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "benchmark": asdict(self.benchmark),
            "environment": {
                "architecture": self.environment_architecture,
                "isa": asdict(self.environment_isa),
            },
            "compiler": None if self.compiler is None else asdict(self.compiler),
            "build": asdict(self.build),
            "implementations": {
                name: result.to_dict()
                for name, result in self.implementations.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def _parse_nonnegative_int(value: str, field: str) -> int:
    if not value.isascii() or not value.isdecimal():
        raise BenchmarkError(f"Benchmark protocol field '{field}' must be a nonnegative integer.")
    return int(value)


def _parse_finite_float(value: str, field: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise BenchmarkError(f"Benchmark protocol field '{field}' must be a number.") from error
    if not math.isfinite(parsed):
        raise BenchmarkError(f"Benchmark protocol field '{field}' must be finite.")
    return parsed


def _parse_record(
    line: str, record_type: str, field_count: int, line_number: int
) -> list[str]:
    fields = line.split("\t")
    if len(fields) != field_count or fields[0] != record_type:
        raise BenchmarkError(
            f"Benchmark protocol line {line_number} must be a {record_type} record "
            f"with {field_count - 1} fields."
        )
    return fields

def experiment_from_benchmark_protocol(
    protocol: str,
    *,
    architecture: str | None,
    compiler: CompilerMetadata | None,
    build: BuildMetadata,
    isa: IsaCapabilities | None = None,
) -> Experiment:
    lines = protocol.splitlines()
    if len(lines) < 3 or lines[0] != RESULT_PROTOCOL_HEADER:
        raise BenchmarkError(
            f"Benchmark did not produce the {RESULT_PROTOCOL_HEADER} result protocol."
        )

    benchmark_fields = _parse_record(lines[1], "benchmark", 6, 2)
    seed = benchmark_fields[5]
    if (
        len(seed) != 18
        or not seed.startswith("0x")
        or not all(character in "0123456789abcdef" for character in seed[2:])
    ):
        raise BenchmarkError("Benchmark protocol field 'benchmark.seed' must be a 64-bit hex value.")
    benchmark = BenchmarkMetadata(
        name=benchmark_fields[1],
        length=_parse_nonnegative_int(benchmark_fields[2], "benchmark.length"),
        warmup_iterations=_parse_nonnegative_int(
            benchmark_fields[3], "benchmark.warmup_iterations"
        ),
        measured_iterations=_parse_nonnegative_int(
            benchmark_fields[4], "benchmark.measured_iterations"
        ),
        seed=seed,
    )

    implementations: dict[str, ImplementationResult] = {}
    for line_number, line in enumerate(lines[2:], start=3):
        fields = _parse_record(line, "implementation", 7, line_number)
        name = fields[1]
        if not name or name in implementations:
            raise BenchmarkError(
                f"Benchmark protocol implementation name on line {line_number} is invalid."
            )
        if fields[2] == "true":
            passed = True
        elif fields[2] == "false":
            passed = False
        else:
            raise BenchmarkError(
                f"Benchmark protocol field 'implementation.{name}.validation' must be true or false."
            )
        implementations[name] = ImplementationResult(
            validation_passed=passed,
            timing=Timing(
                min_ns=_parse_nonnegative_int(fields[3], f"implementation.{name}.min_ns"),
                median_ns=_parse_finite_float(
                    fields[4], f"implementation.{name}.median_ns"
                ),
                mean_ns=_parse_finite_float(fields[5], f"implementation.{name}.mean_ns"),
            ),
            sample_count=_parse_nonnegative_int(
                fields[6], f"implementation.{name}.sample_count"
            ),
        )

    return Experiment(
        benchmark=benchmark,
        environment_architecture=architecture,
        compiler=compiler,
        build=build,
        implementations=implementations,
        environment_isa=IsaCapabilities(vector=None) if isa is None else isa,
    )

def _cmake_value(text: str, name: str) -> str | None:
    match = re.search(rf'^set\({re.escape(name)} "(?P<value>.*)"\)$', text, re.MULTILINE)
    return None if match is None else match.group("value")


def load_compiler_metadata(build_directory: Path) -> CompilerMetadata | None:
    compiler_files = sorted((build_directory / "CMakeFiles").glob("*/CMakeCCompiler.cmake"))
    if not compiler_files:
        return None

    text = compiler_files[-1].read_text(encoding="utf-8")
    return CompilerMetadata(
        name=_cmake_value(text, "CMAKE_C_COMPILER_ID"),
        version=_cmake_value(text, "CMAKE_C_COMPILER_VERSION"),
        path=_cmake_value(text, "CMAKE_C_COMPILER"),
    )


def _compile_flags(entry: dict[str, Any]) -> list[str]:
    command = entry.get("command")
    if not isinstance(command, str):
        return []
    arguments = shlex.split(command)
    if not arguments:
        return []

    source = entry.get("file")
    flags: list[str] = []
    index = 1
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-o":
            index += 2
            continue
        if argument == "-c" or argument == source:
            index += 1
            continue
        flags.append(argument)
        index += 1
    return flags


def load_kernel_compile_flags(
    build_directory: Path, project_root: Path
) -> dict[str, list[str]] | None:
    compile_commands_path = build_directory / "compile_commands.json"
    if not compile_commands_path.is_file():
        return None

    try:
        entries = json.loads(compile_commands_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BenchmarkError(
            f"Could not parse compile commands at {compile_commands_path}: {error.msg}."
        ) from error
    if not isinstance(entries, list):
        raise BenchmarkError(f"Compile commands at {compile_commands_path} must be a JSON array.")

    flags: dict[str, list[str]] = {}
    for name, relative_source in KERNEL_SOURCES.items():
        expected_source = (project_root / relative_source).resolve()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
                continue
            if Path(entry["file"]).resolve() == expected_source:
                flags[name] = _compile_flags(entry)
                break
    return flags


def run_benchmark(
    *,
    binary: Path | None,
    preset: str,
    length: str | None,
    warmup: str | None,
    iterations: str | None,
    seed: str | None,
) -> Experiment:
    binary_path = resolve_binary_path(binary, preset)
    if not binary_path.is_file():
        raise BenchmarkError(f"Benchmark binary does not exist: {binary_path}")

    command = [str(binary_path), "--result-protocol"]
    for option, value in (
        ("--length", length),
        ("--warmup", warmup),
        ("--iterations", iterations),
        ("--seed", seed),
    ):
        if value is not None:
            command.extend((option, value))

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise BenchmarkError(f"Could not run benchmark '{binary_path}': {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip()
        message = f"Benchmark failed with exit status {result.returncode}."
        if detail:
            message = f"{message} {detail}"
        raise BenchmarkError(message)

    project_root = Path(__file__).resolve().parent.parent
    build_directory = binary_path.parent if binary is not None else project_root / "build" / preset
    build = BuildMetadata(
        preset=None if binary is not None else preset,
        kernel_compile_flags=load_kernel_compile_flags(build_directory, project_root),
        vectorization=load_vectorization_reports(build_directory, project_root),
    )
    architecture = platform.machine() or None
    return experiment_from_benchmark_protocol(
        result.stdout,
        architecture=architecture,
        isa=discover_isa_capabilities(architecture),
        compiler=load_compiler_metadata(build_directory),
        build=build,
    )


def render_experiment(experiment: Experiment) -> str:
    benchmark = experiment.benchmark
    lines = [
        f"RCT {benchmark.name}",
        "",
        f"architecture: {experiment.environment_architecture or 'unavailable'}",
        f"length:       {benchmark.length}",
        f"warmup:       {benchmark.warmup_iterations}",
        f"iterations:   {benchmark.measured_iterations}",
        f"seed:         {benchmark.seed}",
        "",
        f"{'implementation':<16} {'valid':<7} {'median ns':<12} {'mean ns':<12} {'min ns':<12} {'samples':<8}",
    ]
    for name, result in experiment.implementations.items():
        lines.append(
            f"{name:<16} {'yes' if result.validation_passed else 'no':<7} "
            f"{result.timing.median_ns:<12.1f} {result.timing.mean_ns:<12.1f} "
            f"{result.timing.min_ns:<12} {result.sample_count:<8}"
        )
    return "\n".join(lines) + "\n"
