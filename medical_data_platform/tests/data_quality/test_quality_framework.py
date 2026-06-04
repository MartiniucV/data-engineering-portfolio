"""
Tests for the custom data quality framework.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.quality_checks import CheckResult, QualityReport


class TestCheckResult:
    def test_creation(self):
        r = CheckResult(
            check_name="test_check",
            table="patients",
            column="patient_id",
            status="PASS",
            metric=0.0,
            threshold=0.05,
            message="OK",
        )
        assert r.check_name == "test_check"
        assert r.status == "PASS"
        assert r.checked_at is not None

    def test_status_options(self):
        for status in ["PASS", "FAIL", "WARN"]:
            r = CheckResult(
                check_name="x", table="t", column="c",
                status=status, metric=None, threshold=None, message="m"
            )
            assert r.status == status


class TestQualityReport:
    def test_empty_report(self):
        r = QualityReport()
        assert r.passed == 0
        assert r.failed == 0
        assert r.warnings == 0

    def test_add_pass(self):
        r = QualityReport()
        r.add(CheckResult("c", "t", None, "PASS", 0.0, 0.05, "ok"))
        assert r.passed == 1
        assert r.failed == 0

    def test_add_fail(self):
        r = QualityReport()
        r.add(CheckResult("c", "t", None, "FAIL", 0.1, 0.05, "fail"))
        assert r.failed == 1

    def test_add_warn(self):
        r = QualityReport()
        r.add(CheckResult("c", "t", None, "WARN", 0.03, 0.05, "warn"))
        assert r.warnings == 1

    def test_mixed_statuses(self):
        r = QualityReport()
        r.add(CheckResult("a", "t", None, "PASS", 0, 0, ""))
        r.add(CheckResult("b", "t", None, "FAIL", 1, 0, ""))
        r.add(CheckResult("c", "t", None, "WARN", 0, 0, ""))
        assert r.passed == 1
        assert r.failed == 1
        assert r.warnings == 1

    def test_save_to_file(self, tmp_path):
        import json
        r = QualityReport()
        r.add(CheckResult("c", "t", "col", "PASS", 0.01, 0.05, "ok"))
        path = tmp_path / "report.json"
        r.save(path)
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert "summary" in data
        assert "results" in data
        assert data["summary"]["passed"] == 1
