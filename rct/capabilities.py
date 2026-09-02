from __future__ import annotations

from dataclasses import dataclass
import ctypes
import errno
from pathlib import Path
import platform
import re


_RISCV_HWPROBE_SYSCALL = 258
_RISCV_HWPROBE_KEY_IMA_EXT_0 = 4
_RISCV_HWPROBE_IMA_V = 1 << 2


@dataclass(frozen=True)
class IsaCapabilities:
    """Runtime ISA capabilities relevant to the experiment."""

    vector: bool | None


class _RiscvHwprobe(ctypes.Structure):
    _fields_ = [("key", ctypes.c_longlong), ("value", ctypes.c_ulonglong)]


def _riscv_hwprobe_vector() -> bool | None:
    """Return RISC-V V support from Linux hwprobe, or None when unavailable."""
    probe = _RiscvHwprobe(_RISCV_HWPROBE_KEY_IMA_EXT_0, 0)
    try:
        result = ctypes.CDLL(None, use_errno=True).syscall(
            _RISCV_HWPROBE_SYSCALL, ctypes.byref(probe), 1, 0, None, 0
        )
    except (AttributeError, OSError):
        return None
    if result == 0:
        return bool(probe.value & _RISCV_HWPROBE_IMA_V)
    if ctypes.get_errno() in (errno.ENOSYS, errno.EINVAL):
        return None
    return None


def _proc_cpuinfo_vector(text: str) -> bool | None:
    """Return RISC-V V support from a kernel-reported ISA line, if present."""
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator == "" or key.strip().lower() != "isa":
            continue
        isa = value.strip().lower()
        match = re.fullmatch(r"rv(?:32|64)([a-z]+)(?:_[a-z0-9]+)*", isa)
        if match is not None:
            return "v" in match.group(1) or "_v" in isa
    return None


def _proc_cpuinfo_vector_from_path(path: Path = Path("/proc/cpuinfo")) -> bool | None:
    try:
        return _proc_cpuinfo_vector(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def discover_isa_capabilities(architecture: str | None = None) -> IsaCapabilities:
    """Discover runtime ISA support without inferring it from compiler options."""
    architecture = platform.machine() if architecture is None else architecture
    if architecture is None or not architecture.lower().startswith("riscv"):
        return IsaCapabilities(vector=None)

    vector = _riscv_hwprobe_vector()
    if vector is None:
        vector = _proc_cpuinfo_vector_from_path()
    return IsaCapabilities(vector=vector)
