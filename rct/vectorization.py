from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


DIAGNOSTIC_ARTIFACTS = {"auto": Path("rct-vectorization") / "auto.opt"}
_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?:(?P<source>.*?):(?P<line>[0-9]+)(?::(?P<column>[0-9]+))?:\s*)?"
    r"(?P<kind>optimized|missed):\s*(?P<message>.+)$"
)


@dataclass(frozen=True)
class VectorizationDiagnostic:
    message: str
    source: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class VectorizationReport:
    available: bool
    optimized: tuple[VectorizationDiagnostic, ...] = ()
    missed: tuple[VectorizationDiagnostic, ...] = ()


def _normalize_source(source: str | None, project_root: Path | None) -> str | None:
    if source is None or project_root is None:
        return source
    try:
        return str(Path(source).resolve().relative_to(project_root.resolve()))
    except ValueError:
        return source


def parse_gcc_vectorization_diagnostics(
    text: str, project_root: Path | None = None
) -> VectorizationReport:
    """Parse GCC vector optimization records without relying on their message text."""
    optimized: list[VectorizationDiagnostic] = []
    missed: list[VectorizationDiagnostic] = []
    for raw_line in text.splitlines():
        match = _DIAGNOSTIC_PATTERN.match(raw_line)
        if match is None:
            continue
        diagnostic = VectorizationDiagnostic(
            message=match.group("message"),
            source=_normalize_source(match.group("source"), project_root),
            line=int(match.group("line")) if match.group("line") is not None else None,
            column=(
                int(match.group("column")) if match.group("column") is not None else None
            ),
        )
        if match.group("kind") == "optimized":
            optimized.append(diagnostic)
        else:
            missed.append(diagnostic)
    return VectorizationReport(
        available=True, optimized=tuple(optimized), missed=tuple(missed)
    )


def load_vectorization_reports(
    build_directory: Path, project_root: Path
) -> dict[str, VectorizationReport]:
    """Load generated compiler reports for kernels configured to emit them."""
    reports: dict[str, VectorizationReport] = {}
    for kernel, relative_path in DIAGNOSTIC_ARTIFACTS.items():
        path = build_directory / relative_path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            reports[kernel] = VectorizationReport(available=False)
        else:
            reports[kernel] = parse_gcc_vectorization_diagnostics(text, project_root)
    return reports
