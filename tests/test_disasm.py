from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from rct import disasm


class ResolveKernelSymbolTests(unittest.TestCase):
    def test_known_aliases_resolve_to_kernel_symbols(self) -> None:
        self.assertEqual(
            disasm.resolve_kernel_symbol("reference"),
            "rct_vector_add_f32_reference",
        )
        self.assertEqual(
            disasm.resolve_kernel_symbol("scalar"),
            "rct_vector_add_f32_scalar",
        )
        self.assertEqual(
            disasm.resolve_kernel_symbol("auto"),
            "rct_vector_add_f32_auto",
        )

    def test_unknown_alias_raises_disassembly_error(self) -> None:
        with self.assertRaisesRegex(disasm.DisassemblyError, "Unknown kernel alias"):
            disasm.resolve_kernel_symbol("invalid")


class FindDisassemblerTests(unittest.TestCase):
    def test_prefers_llvm_objdump(self) -> None:
        with mock.patch(
            "rct.disasm.shutil.which",
            side_effect=lambda name: {
                "llvm-objdump": "/tools/llvm-objdump",
                "objdump": "/tools/objdump",
            }.get(name),
        ):
            self.assertEqual(disasm.find_disassembler(), "/tools/llvm-objdump")

    def test_falls_back_to_gnu_objdump(self) -> None:
        with mock.patch(
            "rct.disasm.shutil.which",
            side_effect=lambda name: {"objdump": "/tools/objdump"}.get(name),
        ):
            self.assertEqual(disasm.find_disassembler(), "/tools/objdump")

    def test_missing_disassembler_reports_installation_guidance(self) -> None:
        with mock.patch("rct.disasm.shutil.which", return_value=None):
            with self.assertRaisesRegex(
                disasm.DisassemblyError,
                "Could not find a supported disassembler",
            ):
                disasm.find_disassembler()


class BuildDisassemblerCommandTests(unittest.TestCase):
    def test_llvm_command_includes_source_and_symbol(self) -> None:
        self.assertEqual(
            disasm.build_disassembler_command(
                "/tools/llvm-objdump",
                "rct_vector_add_f32_auto",
                Path("/tmp/rct_bench"),
                include_source=True,
            ),
            [
                "/tools/llvm-objdump",
                "--source",
                "--disassemble-symbols=rct_vector_add_f32_auto",
                "/tmp/rct_bench",
            ],
        )

    def test_gnu_command_omits_source_when_requested(self) -> None:
        self.assertEqual(
            disasm.build_disassembler_command(
                "/tools/objdump",
                "rct_vector_add_f32_scalar",
                Path("/tmp/rct_bench"),
                include_source=False,
            ),
            [
                "/tools/objdump",
                "--disassemble=rct_vector_add_f32_scalar",
                "/tmp/rct_bench",
            ],
        )


class DisassembleTests(unittest.TestCase):
    def test_missing_binary_raises_disassembly_error(self) -> None:
        with self.assertRaisesRegex(
            disasm.DisassemblyError,
            "Benchmark binary does not exist",
        ):
            disasm.disassemble(
                "auto",
                Path("/missing/rct_bench"),
                "optimized-debug",
                include_source=True,
            )

    def test_failed_disassembler_reports_stderr(self) -> None:
        with TemporaryDirectory() as directory:
            binary = Path(directory) / "rct_bench"
            binary.touch()
            failure = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="unsupported binary"
            )
            with (
                mock.patch(
                    "rct.disasm.find_disassembler", return_value="/tools/objdump"
                ),
                mock.patch("rct.disasm.subprocess.run", return_value=failure),
            ):
                with self.assertRaisesRegex(
                    disasm.DisassemblyError,
                    "failed with exit status 1. unsupported binary",
                ):
                    disasm.disassemble(
                        "auto", binary, "optimized-debug", include_source=True
                    )

    def test_successful_disassembly_returns_stdout(self) -> None:
        with TemporaryDirectory() as directory:
            binary = Path(directory) / "rct_bench"
            binary.touch()
            success = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="disassembly\n", stderr=""
            )
            with (
                mock.patch(
                    "rct.disasm.find_disassembler", return_value="/tools/objdump"
                ),
                mock.patch("rct.disasm.subprocess.run", return_value=success),
            ):
                output = disasm.disassemble(
                    "auto", binary, "optimized-debug", include_source=True
                )

        self.assertEqual(output, "disassembly\n")


if __name__ == "__main__":
    unittest.main()
