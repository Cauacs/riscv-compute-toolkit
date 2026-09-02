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


class CodegenClassifierTests(unittest.TestCase):
    def test_classifies_representative_rvv_setup_load_arithmetic_and_store(self) -> None:
        report = classify_rvv_codegen(RVV_DISASSEMBLY)

        self.assertEqual(
            report,
            CodegenReport(
                available=True,
                rvv_instructions=True,
                isa="rvv",
                recognized_mnemonics=("vsetvli", "vle32.v", "vfadd.vv", "vse32.v"),
            ),
        )

    def test_scalar_riscv_assembly_is_not_classified_as_rvv(self) -> None:
        report = classify_rvv_codegen(SCALAR_DISASSEMBLY)

        self.assertEqual(report, CodegenReport(available=True, rvv_instructions=False))

    def test_empty_or_malformed_disassembly_is_unavailable(self) -> None:
        self.assertEqual(
            classify_rvv_codegen(""),
            CodegenReport(available=False, rvv_instructions=None),
        )
        self.assertEqual(
            classify_rvv_codegen("not disassembly"),
            CodegenReport(available=False, rvv_instructions=None),
        )

    def test_disassembly_failures_do_not_make_benchmark_evidence_fatal(self) -> None:
        with mock.patch(
            "rct.codegen.disassemble", side_effect=DisassemblyError("missing objdump")
        ):
            reports = load_codegen_reports(binary=mock.Mock(), preset="test")

        self.assertEqual(
            reports,
            {
                "scalar": CodegenReport(available=False, rvv_instructions=None),
                "auto": CodegenReport(available=False, rvv_instructions=None),
            },
        )


if __name__ == "__main__":
    unittest.main()
