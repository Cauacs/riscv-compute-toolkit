import ctypes
import unittest
from unittest import mock

from rct.capabilities import (
    IsaCapabilities,
    _RiscvHwprobe,
    _proc_cpuinfo_vector,
    _riscv_hwprobe_vector,
    discover_isa_capabilities,
)


class CapabilityDiscoveryTests(unittest.TestCase):
    def test_non_riscv_host_leaves_vector_support_unknown(self) -> None:
        with mock.patch("rct.capabilities._riscv_hwprobe_vector") as hwprobe:
            capabilities = discover_isa_capabilities("x86_64")

        self.assertEqual(capabilities, IsaCapabilities(vector=None))
        hwprobe.assert_not_called()

    def test_kernel_reported_isa_distinguishes_vector_support(self) -> None:
        self.assertTrue(_proc_cpuinfo_vector("isa\t: rv64imafdcv_zicsr\n"))
        self.assertFalse(_proc_cpuinfo_vector("isa\t: rv64imafdc_zicsr\n"))

    def test_malformed_or_absent_isa_is_unknown(self) -> None:
        self.assertIsNone(_proc_cpuinfo_vector("isa: not-an-isa\n"))
        self.assertIsNone(_proc_cpuinfo_vector("model name: unknown\n"))

    def test_hwprobe_result_takes_precedence_over_cpuinfo_fallback(self) -> None:
        with (
            mock.patch("rct.capabilities._riscv_hwprobe_vector", return_value=False),
            mock.patch("rct.capabilities._proc_cpuinfo_vector_from_path") as cpuinfo,
        ):
            capabilities = discover_isa_capabilities("riscv64")

        self.assertEqual(capabilities, IsaCapabilities(vector=False))
        cpuinfo.assert_not_called()

    def test_unknown_hwprobe_key_is_not_reported_as_missing_vector_support(self) -> None:
        def syscall(*arguments: object) -> int:
            probe = ctypes.cast(
                arguments[1], ctypes.POINTER(_RiscvHwprobe)
            ).contents
            probe.key = -1
            return 0

        library = mock.Mock()
        library.syscall.side_effect = syscall
        with mock.patch("rct.capabilities.ctypes.CDLL", return_value=library):
            self.assertIsNone(_riscv_hwprobe_vector())

    def test_unavailable_hwprobe_uses_kernel_isa_fallback(self) -> None:
        with (
            mock.patch("rct.capabilities._riscv_hwprobe_vector", return_value=None),
            mock.patch("rct.capabilities._proc_cpuinfo_vector_from_path", return_value=True),
        ):
            capabilities = discover_isa_capabilities("riscv64")

        self.assertEqual(capabilities, IsaCapabilities(vector=True))


if __name__ == "__main__":
    unittest.main()
