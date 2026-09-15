from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any

from rct.capabilities import IsaCapabilities
from rct.codegen import CodegenReport
from rct.vectorization import VectorizationReport


SCHEMA_VERSION = "1.3"


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
    codegen: dict[str, CodegenReport] | None = None
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
            "codegen": (
                None
                if self.codegen is None
                else {kernel: asdict(report) for kernel, report in self.codegen.items()}
            ),
            "implementations": {
                name: result.to_dict()
                for name, result in self.implementations.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


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
