from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
from typing import Any, Mapping

from rct.experiment import CompilerMetadata


class BuildMetadataError(RuntimeError):
    """Raised when configured build metadata cannot be interpreted."""


def _cmake_value(text: str, name: str) -> str | None:
    match = re.search(rf'^set\({re.escape(name)} "(?P<value>.*)"\)$', text, re.MULTILINE)
    return None if match is None else match.group("value")


def load_compiler_metadata(build_directory: Path) -> CompilerMetadata | None:
    compiler_files = sorted(
        (build_directory / "CMakeFiles").glob("*/CMakeCCompiler.cmake")
    )
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
    build_directory: Path,
    project_root: Path,
    kernel_sources: Mapping[str, str],
) -> dict[str, list[str]] | None:
    compile_commands_path = build_directory / "compile_commands.json"
    if not compile_commands_path.is_file():
        return None

    try:
        entries = json.loads(compile_commands_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BuildMetadataError(
            f"Could not parse compile commands at {compile_commands_path}: {error.msg}."
        ) from error
    if not isinstance(entries, list):
        raise BuildMetadataError(
            f"Compile commands at {compile_commands_path} must be a JSON array."
        )

    flags: dict[str, list[str]] = {}
    for name, relative_source in kernel_sources.items():
        expected_source = (project_root / relative_source).resolve()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
                continue
            if Path(entry["file"]).resolve() == expected_source:
                flags[name] = _compile_flags(entry)
                break
    return flags
