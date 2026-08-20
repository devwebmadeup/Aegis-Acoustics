"""Regression checks for the repository's public evidence-boundary contract."""

import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
README = REPOSITORY_ROOT / "README.md"
DOCS_README = REPOSITORY_ROOT / "docs" / "README.md"
WHITEPAPER = REPOSITORY_ROOT / "docs" / "Aegis_Acoustics_B2B_Whitepaper.md"
EVIDENCE = REPOSITORY_ROOT / "docs" / "FEASIBILITY_EVIDENCE.md"
MODEL_SELECTION = REPOSITORY_ROOT / "docs" / "MODEL_SELECTION.md"
PROTOCOL_CONFIG = REPOSITORY_ROOT / "examples" / "deposition_protocol_config.json"
PROTOCOL_TEMPLATE = REPOSITORY_ROOT / "examples" / "deposition_protocol_template.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class PublicClaimBoundaryTests(unittest.TestCase):
    def test_whitepaper_frontloads_product_no_go_and_zero_hardware_data(self):
        document = read(WHITEPAPER)
        opening = document[:2500]
        for required in (
            "제품·하드웨어 성능 미검증",
            "제품 및 고객 적용 NO-GO",
            "실측 데이터는 0건",
            "구매·투자",
            "10–50 nm",
            "HVAC",
        ):
            with self.subTest(required=required):
                self.assertIn(required, opening)
        self.assertLess(
            document.index("제품·하드웨어 성능 미검증"),
            document.index("## 1. 30초 판정"),
        )
        self.assertNotIn("Conditional GO", document)

    def test_whitepaper_defines_software_terms_without_hardware_promotion(self):
        document = read(WHITEPAPER)
        for required in (
            "`verified`",
            "`passed=true`",
            "dataset-rule pass",
            "hardware-validation pass가 아닙니다",
            "`validated`",
            "`experimental`",
            "`NO-GO`",
            "`device_performance_validated=false`",
            "`actual_bootstrap_gate_validated=false`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, document)

    def test_prominent_numbers_have_local_nonperformance_limits(self):
        document = read(WHITEPAPER)
        number_table_start = document.index("## 4. 핵심 수치를 읽는 법")
        number_table_end = document.index("## 5. 기술 트랙별 현재 상태")
        number_table = document[number_table_start:number_table_end]
        for number in ("0.406°", "69.444 ns", "124.8 nm", "약 150 nm", "23 + 23", "약 0.83"):
            with self.subTest(number=number):
                self.assertIn(number, number_table)
        for limitation in (
            "하드웨어 정확도",
            "최소 제어 크기",
            "Aegis 배열 성능",
            "실제 bootstrap power 보장",
            "물리 SD",
        ):
            with self.subTest(limitation=limitation):
                self.assertIn(limitation, number_table)

    def test_whitepaper_contains_safety_business_and_evidence_gates(self):
        document = read(WHITEPAPER)
        for required in (
            "현재 0/8 완료",
            "가청음·초음파·고조파",
            "ESD",
            "EMC",
            "interlock·fault injection",
            "outgassing",
            "CAPEX",
            "OPEX",
            "ROI",
            "IP/FTO",
            "actual gate를 calibration",
        ):
            with self.subTest(required=required):
                self.assertIn(required, document)

    def test_readme_and_evidence_repeat_the_product_boundary(self):
        readme = read(README)
        evidence = read(EVIDENCE)
        for name, document in (("README", readme), ("evidence", evidence)):
            with self.subTest(document=name):
                self.assertIn("제품·고객 적용 판정: NO-GO", document)
                self.assertIn("실측", document)
                self.assertIn("0건", document)
                self.assertIn("dataset-rule pass", document)
        self.assertIn("software-reproducibility fixture", readme)
        self.assertIn("software-reproducibility fixture", evidence)

    def test_shipped_deposition_protocol_is_a_300_nm_nonexecution_fixture(self):
        config = json.loads(PROTOCOL_CONFIG.read_text(encoding="utf-8"))
        locked = json.loads(PROTOCOL_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(config["planning_inputs"]["particle_nm"], 300.0)
        self.assertTrue(config["protocol"]["example_only"])
        self.assertEqual(locked["planning_inputs"]["particle_nm"], 300.0)
        self.assertTrue(locked["protocol"]["example_only"])
        self.assertFalse(locked["protocol"]["execution_eligible"])
        self.assertIn("EXAMPLE-ONLY", locked["protocol"]["protocol_id"])

    def test_all_local_markdown_links_resolve(self):
        markdown_files = (
            README,
            DOCS_README,
            WHITEPAPER,
            EVIDENCE,
            MODEL_SELECTION,
        )
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        failures = []
        for markdown_file in markdown_files:
            for raw_target in link_pattern.findall(read(markdown_file)):
                target = raw_target.strip().strip("<>")
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path_text = target.split("#", 1)[0]
                if not path_text:
                    continue
                resolved = (markdown_file.parent / path_text).resolve()
                if not resolved.exists():
                    failures.append(f"{markdown_file.relative_to(REPOSITORY_ROOT)} -> {target}")
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
