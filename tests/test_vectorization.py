from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rct.vectorization import (
    VectorizationReport,
    load_vectorization_reports,
    parse_gcc_vectorization_diagnostics,
)


class VectorizationDiagnosticTests(unittest.TestCase):
    def test_gcc_records_preserve_category_message_and_location(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            text = "\n".join(
                (
                    f"{root}/src/kernels/vector_add_auto.c:9:31: optimized: loop vectorized using 16 byte vectors",
                    f"{root}/src/kernels/vector_add_auto.c:9:31: missed: not vectorized: relevant statement not supported",
                )
            )
            report = parse_gcc_vectorization_diagnostics(text, root)

        self.assertTrue(report.available)
        self.assertEqual(len(report.optimized), 1)
        self.assertEqual(report.optimized[0].source, "src/kernels/vector_add_auto.c")
        self.assertEqual(report.optimized[0].line, 9)
        self.assertEqual(report.optimized[0].column, 31)
        self.assertEqual(
            report.optimized[0].message, "loop vectorized using 16 byte vectors"
        )
        self.assertEqual(len(report.missed), 1)
        self.assertEqual(
            report.missed[0].message,
            "not vectorized: relevant statement not supported",
        )

    def test_malformed_diagnostics_are_ignored(self) -> None:
        report = parse_gcc_vectorization_diagnostics(
            "unrelated compiler output\nsource.c:not-a-line: optimized: ignored\n"
        )

        self.assertTrue(report.available)
        self.assertEqual(report.optimized, ())
        self.assertEqual(report.missed, ())

    def test_missing_artifact_is_reported_as_unavailable(self) -> None:
        with TemporaryDirectory() as directory:
            reports = load_vectorization_reports(Path(directory), Path(directory))

        self.assertEqual(reports, {"auto": VectorizationReport(available=False)})

    def test_artifact_is_loaded_for_the_auto_kernel(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "rct-vectorization" / "auto.opt"
            artifact.parent.mkdir()
            artifact.write_text("auto.c:2: optimized: loop vectorized\n", encoding="utf-8")
            reports = load_vectorization_reports(root, root)

        self.assertTrue(reports["auto"].available)
        self.assertEqual(reports["auto"].optimized[0].source, "auto.c")
        self.assertEqual(reports["auto"].optimized[0].line, 2)


if __name__ == "__main__":
    unittest.main()
