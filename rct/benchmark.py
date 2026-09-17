from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import platform
import subprocess

from rct.build_metadata import (
    BuildMetadataError,
    load_compiler_metadata,
    load_kernel_compile_flags,
)
from rct.capabilities import IsaCapabilities, discover_isa_capabilities
from rct.codegen import CodegenReport, load_codegen_reports
from rct.disasm import resolve_binary_path
from rct.experiment import (
    BenchmarkMetadata,
    BuildMetadata,
    CompilerMetadata,
    Experiment,
    ImplementationResult,
    Timing,
)
from rct.vectorization import load_vectorization_reports


RESULT_PROTOCOL_HEADER = "rct-benchmark-result-v2"


class BenchmarkError(RuntimeError):
    """Raised when benchmark execution or result data cannot be interpreted."""


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
    codegen: dict[str, CodegenReport] | None = None,
) -> Experiment:
    lines = protocol.splitlines()
    if len(lines) < 3 or lines[0] != RESULT_PROTOCOL_HEADER:
        raise BenchmarkError(
            f"Benchmark did not produce the {RESULT_PROTOCOL_HEADER} result protocol."
        )

    benchmark_fields = _parse_record(lines[1], "benchmark", 6, 2)
    if not benchmark_fields[1]:
        raise BenchmarkError("Benchmark protocol field 'benchmark.name' must not be empty.")
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

    records: dict[str, tuple[str, bool, int, float, float, int]] = {}
    samples: dict[str, list[int]] = {}
    parsing_samples = False
    for line_number, line in enumerate(lines[2:], start=3):
        record_type = line.split("\t", 1)[0]
        if record_type == "implementation":
            if parsing_samples:
                raise BenchmarkError(
                    f"Benchmark protocol implementation record on line {line_number} "
                    "must precede all sample records."
                )
            fields = _parse_record(line, "implementation", 8, line_number)
            name = fields[1]
            source_path = fields[2]
            if not name or name in records:
                raise BenchmarkError(
                    f"Benchmark protocol implementation name on line {line_number} is invalid."
                )
            if not source_path:
                raise BenchmarkError(
                    f"Benchmark protocol field 'implementation.{name}.source_path' "
                    "must not be empty."
                )
            if fields[3] == "true":
                passed = True
            elif fields[3] == "false":
                passed = False
            else:
                raise BenchmarkError(
                    f"Benchmark protocol field 'implementation.{name}.validation' "
                    "must be true or false."
                )
            records[name] = (
                source_path,
                passed,
                _parse_nonnegative_int(fields[4], f"implementation.{name}.min_ns"),
                _parse_finite_float(fields[5], f"implementation.{name}.median_ns"),
                _parse_finite_float(fields[6], f"implementation.{name}.mean_ns"),
                _parse_nonnegative_int(fields[7], f"implementation.{name}.sample_count"),
            )
            samples[name] = []
            continue

        parsing_samples = True
        fields = _parse_record(line, "sample", 4, line_number)
        name = fields[1]
        if name not in records:
            raise BenchmarkError(
                f"Benchmark protocol sample on line {line_number} has an unknown implementation."
            )
        sample_count = records[name][5]
        if len(samples[name]) >= sample_count:
            raise BenchmarkError(
                f"Benchmark protocol implementation '{name}' has excess sample records."
            )
        index = _parse_nonnegative_int(fields[2], f"sample.{name}.index")
        if index != len(samples[name]):
            raise BenchmarkError(
                f"Benchmark protocol sample index for implementation '{name}' on line "
                f"{line_number} is out of order."
            )
        samples[name].append(
            _parse_nonnegative_int(fields[3], f"sample.{name}.elapsed_ns")
        )

    if not records:
        raise BenchmarkError("Benchmark protocol must contain at least one implementation.")

    implementations: dict[str, ImplementationResult] = {}
    for name, (source_path, passed, minimum, median, mean, sample_count) in records.items():
        if len(samples[name]) != sample_count:
            raise BenchmarkError(
                f"Benchmark protocol implementation '{name}' is missing sample records."
            )
        implementations[name] = ImplementationResult(
            source_path=source_path,
            validation_passed=passed,
            timing=Timing(
                min_ns=minimum,
                median_ns=median,
                mean_ns=mean,
                samples_ns=tuple(samples[name]),
            ),
            sample_count=sample_count,
        )

    return Experiment(
        benchmark=benchmark,
        environment_architecture=architecture,
        compiler=compiler,
        build=build,
        implementations=implementations,
        environment_isa=IsaCapabilities(vector=None) if isa is None else isa,
        codegen=codegen,
    )


def run_benchmark(
    *,
    binary: Path | None,
    preset: str,
    benchmark: str,
    length: str | None,
    warmup: str | None,
    iterations: str | None,
    seed: str | None,
) -> Experiment:
    binary_path = resolve_binary_path(binary, preset)
    if not binary_path.is_file():
        raise BenchmarkError(f"Benchmark binary does not exist: {binary_path}")

    command = [str(binary_path), "--benchmark", benchmark, "--result-protocol"]
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
    architecture = platform.machine() or None
    experiment = experiment_from_benchmark_protocol(
        result.stdout,
        architecture=architecture,
        isa=discover_isa_capabilities(architecture),
        compiler=None,
        build=BuildMetadata(
            preset=None if binary is not None else preset,
            kernel_compile_flags=None,
        ),
    )
    try:
        build = BuildMetadata(
            preset=None if binary is not None else preset,
            kernel_compile_flags=load_kernel_compile_flags(
                build_directory,
                project_root,
                {
                    name: implementation.source_path
                    for name, implementation in experiment.implementations.items()
                },
            ),
            vectorization=load_vectorization_reports(build_directory, project_root),
        )
        compiler = load_compiler_metadata(build_directory)
    except BuildMetadataError as error:
        raise BenchmarkError(str(error)) from error

    return replace(
        experiment,
        compiler=compiler,
        build=build,
        codegen=load_codegen_reports(binary_path, preset),
    )
