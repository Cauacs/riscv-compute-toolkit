import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from rct import cli
from rct.benchmark import (
    BenchmarkError,
    BuildMetadata,
    CompilerMetadata,
    experiment_from_benchmark_protocol,
    load_compiler_metadata,
    load_kernel_compile_flags,
    run_benchmark,
)
from rct.disasm import DEFAULT_PRESET, resolve_binary_path



BENCHMARK_PROTOCOL = "\n".join(
    (
        "rct-benchmark-result-v1",
        "benchmark\tvector_add_f32\t16\t2\t4\t0x0000000000000001",
        "implementation\treference\ttrue\t10\t12.5\t13\t4",
        "implementation\tauto\ttrue\t8\t9\t9.5\t4",
        "",
    )
)


def make_experiment():
    return experiment_from_benchmark_protocol(
        BENCHMARK_PROTOCOL,
        architecture=None,
        compiler=None,
        build=BuildMetadata(preset="test", kernel_compile_flags=None),
    )


class ExperimentTests(unittest.TestCase):
    def test_experiment_json_is_versioned_and_preserves_results(self) -> None:
        document = json.loads(make_experiment().to_json())

        self.assertEqual(document["schema_version"], "1.0")
        self.assertEqual(
            document["benchmark"],
            {
                "name": "vector_add_f32",
                "length": 16,
                "warmup_iterations": 2,
                "measured_iterations": 4,
                "seed": "0x0000000000000001",
            },
        )
        self.assertEqual(
            document["implementations"]["auto"],
            {
                "validation": {"passed": True},
                "timing": {"min_ns": 8, "median_ns": 9.0, "mean_ns": 9.5},
                "sample_count": 4,
            },
        )
        self.assertIsNone(document["environment"]["architecture"])
        self.assertIsNone(document["compiler"])
        self.assertIsNone(document["build"]["kernel_compile_flags"])

    def test_result_protocol_rejects_non_protocol_input(self) -> None:
        with self.assertRaisesRegex(BenchmarkError, "result protocol"):
            experiment_from_benchmark_protocol(
                "{\"benchmark\": {}}",
                architecture=None,
                compiler=None,
                build=BuildMetadata(preset="test", kernel_compile_flags=None),
            )

    def test_cmake_metadata_keeps_flags_per_kernel(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            build_directory = project_root / "build" / "test"
            compiler_directory = build_directory / "CMakeFiles" / "4.4.2"
            compiler_directory.mkdir(parents=True)
            (compiler_directory / "CMakeCCompiler.cmake").write_text(
                'set(CMAKE_C_COMPILER "/usr/bin/cc")\n'
                'set(CMAKE_C_COMPILER_ID "GNU")\n'
                'set(CMAKE_C_COMPILER_VERSION "16.2.1")\n',
                encoding="utf-8",
            )
            source = project_root / "src/kernels/vector_add_auto.c"
            compile_commands = [
                {
                    "directory": str(build_directory),
                    "command": f"/usr/bin/cc -O2 -O3 -ftree-vectorize -o auto.o -c {source}",
                    "file": str(source),
                }
            ]
            (build_directory / "compile_commands.json").write_text(
                json.dumps(compile_commands), encoding="utf-8"
            )

            compiler = load_compiler_metadata(build_directory)
            flags = load_kernel_compile_flags(build_directory, project_root)

        self.assertEqual(
            compiler,
            CompilerMetadata(name="GNU", version="16.2.1", path="/usr/bin/cc"),
        )
        self.assertEqual(flags, {"auto": ["-O2", "-O3", "-ftree-vectorize"]})

    def test_explicit_binary_omits_unverified_preset(self) -> None:
        with TemporaryDirectory() as directory:
            binary = Path(directory) / "rct_vector_add_bench"
            binary.touch()
            result = mock.Mock(
                returncode=0,
                stdout=BENCHMARK_PROTOCOL,
                stderr="",
            )
            with mock.patch("rct.benchmark.subprocess.run", return_value=result):
                experiment = run_benchmark(
                    binary=binary,
                    preset="optimized-debug",
                    length=None,
                    warmup=None,
                    iterations=None,
                    seed=None,
                )

        self.assertIsNone(experiment.build.preset)


class BenchmarkProtocolIntegrationTests(unittest.TestCase):
    def test_real_benchmark_protocol_parses(self) -> None:
        binary = resolve_binary_path(None, DEFAULT_PRESET)
        if not binary.is_file():
            self.skipTest(f"Built benchmark is unavailable: {binary}")

        result = subprocess.run(
            [
                str(binary),
                "--result-protocol",
                "--length",
                "8",
                "--warmup",
                "0",
                "--iterations",
                "1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        experiment = experiment_from_benchmark_protocol(
            result.stdout,
            architecture=None,
            compiler=None,
            build=BuildMetadata(preset=DEFAULT_PRESET, kernel_compile_flags=None),
        )

        self.assertEqual(experiment.benchmark.name, "vector_add_f32")
        self.assertEqual(experiment.benchmark.length, 8)
        self.assertEqual(
            list(experiment.implementations), ["reference", "scalar", "auto"]
        )
        self.assertTrue(
            all(result.validation_passed for result in experiment.implementations.values())
        )


class BenchmarkCliTests(unittest.TestCase):
    def test_json_flag_writes_canonical_experiment_document(self) -> None:
        stdout = StringIO()
        with mock.patch("rct.cli.run_benchmark", return_value=make_experiment()):
            with redirect_stdout(stdout):
                result = cli.main(["benchmark", "--json"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["schema_version"], "1.0")

    def test_human_output_remains_available(self) -> None:
        stdout = StringIO()
        with mock.patch("rct.cli.run_benchmark", return_value=make_experiment()):
            with redirect_stdout(stdout):
                result = cli.main(["benchmark"])

        self.assertEqual(result, 0)
        self.assertIn("RCT vector_add_f32", stdout.getvalue())
        self.assertIn("reference", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
