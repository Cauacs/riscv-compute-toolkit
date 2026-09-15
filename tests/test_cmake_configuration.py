import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("cmake"), "CMake is required")
class RvvConfigurationPlumbingTests(unittest.TestCase):
    """Verify generated commands only; these tests do not compile RISC-V objects."""
    def configure(self, *definitions: str) -> tuple[subprocess.CompletedProcess[str], Path]:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        build_directory = Path(directory.name) / "build"
        result = subprocess.run(
            [
                "cmake",
                "-S",
                str(PROJECT_ROOT),
                "-B",
                str(build_directory),
                "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                *definitions,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result, build_directory

    def compile_commands(self, build_directory: Path) -> dict[str, str]:
        entries = json.loads(
            (build_directory / "compile_commands.json").read_text(encoding="utf-8")
        )
        return {
            Path(entry["file"]).name: entry["command"]
            for entry in entries
            if Path(entry["file"]).parent.name == "kernels"
        }

    def test_baseline_configuration_emits_no_riscv_target_flags(self) -> None:
        result, build_directory = self.configure("-DRCT_SOURCE_DEBUG=OFF")
        self.assertEqual(result.returncode, 0, result.stderr)

        commands = self.compile_commands(build_directory)
        self.assertNotIn("-march=rv", commands["vector_add_scalar.c"])
        self.assertNotIn("-march=rv", commands["vector_add_auto.c"])
        self.assertIn("-fno-tree-vectorize", commands["vector_add_scalar.c"])
        self.assertIn("-ftree-vectorize", commands["vector_add_auto.c"])

    def test_rvv_configuration_emits_expected_compile_flags(self) -> None:
        result, build_directory = self.configure(
            "-DCMAKE_SYSTEM_NAME=Linux",
            "-DCMAKE_SYSTEM_PROCESSOR=riscv64",
            "-DRCT_ENABLE_RVV=ON",
            "-DRCT_RISCV_ARCH=rv64gcv",
            "-DRCT_RISCV_ABI=lp64d",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        commands = self.compile_commands(build_directory)
        scalar = commands["vector_add_scalar.c"]
        auto = commands["vector_add_auto.c"]
        reference = commands["vector_add_reference.c"]
        self.assertIn("-march=rv64gcv", scalar)
        self.assertIn("-march=rv64gcv", auto)
        self.assertNotIn("-march=rv64gcv", reference)
        self.assertIn("-mabi=lp64d", scalar)
        self.assertIn("-mabi=lp64d", auto)
        self.assertIn("-fno-tree-vectorize", scalar)
        self.assertIn("-ftree-vectorize", auto)

    def test_rvv_configuration_rejects_a_non_riscv_target(self) -> None:
        result, _ = self.configure(
            "-DCMAKE_SYSTEM_NAME=Linux",
            "-DCMAKE_SYSTEM_PROCESSOR=x86_64",
            "-DRCT_ENABLE_RVV=ON",
            "-DRCT_RISCV_ARCH=rv64gcv",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a RISC-V target system", result.stderr)


if __name__ == "__main__":
    unittest.main()
