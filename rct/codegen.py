from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from rct.disasm import DisassemblyError, disassemble


CODEGEN_KERNELS = ("scalar", "auto")
_DISASSEMBLY_HEADER = re.compile(
    r"^\s*[0-9a-fA-F]+\s+<[^>\n]+>:\s*$", re.MULTILINE
)
_INSTRUCTION = re.compile(
    r"^\s*[0-9a-fA-F]+:\s+(?:(?:[0-9a-fA-F]{2,8})\s+)+"
    r"(?P<mnemonic>[A-Za-z][A-Za-z0-9.]*)\b",
    re.MULTILINE,
)
_RVV_MNEMONIC = re.compile(
    r"^(?:"
    r"vset(?:vli|ivli|vl)|"
    r"vl(?:e|se|uxei|oxei)[0-9]*(?:ff)?\.v|"
    r"vs(?:e|se|uxei|oxei)[0-9]*\.v|"
    r"v(?:fadd|add|fsub|sub|fmul|mul|fdiv|div|fmacc|macc|fmsac|msac|"
    r"fnmacc|nmacc|fnmsac|nmsac)\.[a-z0-9]+"
    r")$"
)


@dataclass(frozen=True)
class CodegenReport:
    available: bool
    rvv_instructions: bool | None
    isa: str | None = None
    recognized_mnemonics: tuple[str, ...] = ()


def classify_rvv_codegen(disassembly: str) -> CodegenReport:
    """Classify a single function's disassembly using narrow RVV mnemonic families."""
    if _DISASSEMBLY_HEADER.search(disassembly) is None:
        return CodegenReport(available=False, rvv_instructions=None)

    mnemonics = [
        match.group("mnemonic").lower()
        for match in _INSTRUCTION.finditer(disassembly)
    ]
    if not mnemonics:
        return CodegenReport(available=False, rvv_instructions=None)

    recognized = tuple(
        dict.fromkeys(mnemonic for mnemonic in mnemonics if _RVV_MNEMONIC.match(mnemonic))
    )
    if recognized:
        return CodegenReport(
            available=True,
            rvv_instructions=True,
            isa="rvv",
            recognized_mnemonics=recognized,
        )
    return CodegenReport(available=True, rvv_instructions=False)


def load_codegen_reports(
    binary: Path, preset: str
) -> dict[str, CodegenReport]:
    """Inspect control and auto kernels without making disassembly availability fatal."""
    reports: dict[str, CodegenReport] = {}
    for kernel in CODEGEN_KERNELS:
        try:
            assembly = disassemble(kernel, binary, preset, include_source=False)
        except DisassemblyError:
            reports[kernel] = CodegenReport(available=False, rvv_instructions=None)
        else:
            reports[kernel] = classify_rvv_codegen(assembly)
    return reports
