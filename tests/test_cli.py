from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import unittest
from unittest import mock

from rct import cli
from rct.disasm import DisassemblyError



class MainTests(unittest.TestCase):
    def test_single_disassembly_preserves_raw_stdout(self) -> None:
        stdout = StringIO()
        with (
            mock.patch("rct.cli.disassemble", return_value="\nraw output\n\n"),
            redirect_stdout(stdout),
        ):
            result = cli.main(["disasm", "auto"])

        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "\nraw output\n\n")

    def test_multiple_disassemblies_render_labeled_sections(self) -> None:
        stdout = StringIO()
        with (
            mock.patch(
                "rct.cli.disassemble",
                side_effect=["reference\n", "scalar", ""],
            ),
            redirect_stdout(stdout),
        ):
            result = cli.main(["disasm", "reference", "scalar", "auto"])

        self.assertEqual(result, 0)
        self.assertEqual(
            stdout.getvalue(),
            "===== reference =====\nreference\n\n"
            "===== scalar =====\nscalar\n\n"
            "===== auto =====\n\n",
        )


    def test_disassembly_error_prevents_partial_stdout(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with (
            mock.patch(
                "rct.cli.disassemble",
                side_effect=["first result\n", DisassemblyError("later failure")],
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as exit_context,
        ):
            cli.main(["disasm", "reference", "scalar"])

        self.assertEqual(exit_context.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
