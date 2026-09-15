import unittest
from unittest import mock

from rct.codegen import CodegenReport, classify_rvv_codegen, load_codegen_reports
from rct.disasm import DisassemblyError


RVV_DISASSEMBLY = """\
0000000000000000 <rct_vector_add_f32_auto>:
   0:   0d857557                vsetvli a0,a0,e32,m1,ta,ma
   4:   02056087                vle32.v v1,(a0)
   8:   0205e107                vle32.v v2,(a1)
   c:   0220d157                vfadd.vv v2,v1,v2
  10:   02066127                vse32.v v2,(a2)
"""
SCALAR_DISASSEMBLY = """\
0000000000000000 <rct_vector_add_f32_scalar>:
   0:   00b50533                add a0,a0,a1
   4:   00008067                ret
"""
UNRECOGNIZED_RVV_DISASSEMBLY = """\
0000000000000000 <rct_vector_add_f32_auto>:
   0:   5e015057                vcompress.vm v0,v1,v2
   4:   00008067                ret
"""


class CodegenClassifierTests(unittest.TestCase):
    def test_recognizes_representative_rvv_setup_load_arithmetic_and_store(self) -> None:
        report = classify_rvv_codegen(RVV_DISASSEMBLY)

        self.assertEqual(
            report,
            CodegenReport(
                available=True,
                recognized_rvv=True,
                recognized_mnemonics=("vsetvli", "vle32.v", "vfadd.vv", "vse32.v"),
            ),
        )

    def test_scalar_riscv_assembly_reports_no_recognized_rvv(self) -> None:
        report = classify_rvv_codegen(SCALAR_DISASSEMBLY)

        self.assertEqual(
            report,
            CodegenReport(available=True, recognized_rvv=False),
        )

    def test_unrecognized_vector_mnemonic_does_not_claim_scalar_codegen(self) -> None:
        report = classify_rvv_codegen(UNRECOGNIZED_RVV_DISASSEMBLY)

        self.assertTrue(report.available)
        self.assertFalse(report.recognized_rvv)
        self.assertEqual(report.recognized_mnemonics, ())

    def test_empty_or_malformed_disassembly_is_unavailable(self) -> None:
        self.assertEqual(
            classify_rvv_codegen(""),
            CodegenReport(available=False, recognized_rvv=None),
        )
        self.assertEqual(
            classify_rvv_codegen("not disassembly"),
            CodegenReport(available=False, recognized_rvv=None),
        )

    def test_disassembly_failures_do_not_make_benchmark_evidence_fatal(self) -> None:
        with mock.patch(
            "rct.codegen.disassemble", side_effect=DisassemblyError("missing objdump")
        ):
            reports = load_codegen_reports(binary=mock.Mock(), preset="test")

        self.assertEqual(
            reports,
            {
                "scalar": CodegenReport(available=False, recognized_rvv=None),
                "auto": CodegenReport(available=False, recognized_rvv=None),
            },
        )


if __name__ == "__main__":
    unittest.main()
