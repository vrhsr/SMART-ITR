"""
Extraction accuracy test harness.

This test measures per-field accuracy of the SmartITR extraction pipeline
against known ground-truth values from sample Form 16 documents.

Usage:
    1. Place sample Form 16 PDFs in tests/fixtures/form16/
    2. Create a ground_truth.json file mapping filename -> expected field values
    3. Run: pytest tests/test_extraction_accuracy.py -v

The test will:
    - Run each PDF through the extraction pipeline
    - Compare extracted values to ground truth
    - Report per-field accuracy percentages
    - FAIL if overall accuracy < 95%
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Only run if fixture directory exists with sample PDFs
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "form16"
GROUND_TRUTH_FILE = FIXTURES_DIR / "ground_truth.json"

# Fields to measure accuracy on
TARGET_FIELDS = [
    "gross_salary",
    "tds_deducted",
    "employer_tan",
    "standard_deduction",
    "employee_pan",
]

ACCURACY_THRESHOLD = 0.95  # 95% minimum required


def load_ground_truth() -> dict:
    """Load ground truth field values from JSON."""
    if not GROUND_TRUTH_FILE.exists():
        return {}
    with open(GROUND_TRUTH_FILE) as f:
        return json.load(f)


def get_sample_pdfs() -> list[Path]:
    """Get all sample Form 16 PDFs from fixtures directory."""
    if not FIXTURES_DIR.exists():
        return []
    return sorted(FIXTURES_DIR.glob("*.pdf"))


def values_match(extracted, expected) -> bool:
    """Compare extracted value to expected, handling numeric tolerance."""
    if extracted is None:
        return False

    # String comparison (case-insensitive, whitespace-stripped)
    if isinstance(expected, str):
        return str(extracted).strip().upper() == expected.strip().upper()

    # Numeric comparison with ±1% tolerance
    if isinstance(expected, (int, float)):
        try:
            ext_val = float(extracted)
            return abs(ext_val - expected) <= max(abs(expected) * 0.01, 1.0)
        except (ValueError, TypeError):
            return False

    return str(extracted) == str(expected)


class TestExtractionAccuracy:
    """Extraction accuracy measurement suite."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Load ground truth and check prerequisites."""
        self.ground_truth = load_ground_truth()
        self.sample_pdfs = get_sample_pdfs()

    @pytest.mark.skipif(
        not FIXTURES_DIR.exists() or not GROUND_TRUTH_FILE.exists(),
        reason="No sample Form 16 PDFs or ground_truth.json found in tests/fixtures/form16/",
    )
    def test_field_level_accuracy(self):
        """
        Run extraction on each sample PDF and measure per-field accuracy.

        Gate: ALL target fields must achieve >= 95% accuracy.
        """
        if not self.sample_pdfs:
            pytest.skip("No sample PDFs found")

        field_correct: dict[str, int] = {f: 0 for f in TARGET_FIELDS}
        field_total: dict[str, int] = {f: 0 for f in TARGET_FIELDS}

        for pdf_path in self.sample_pdfs:
            filename = pdf_path.name
            if filename not in self.ground_truth:
                continue

            expected = self.ground_truth[filename]

            # NOTE: In a real test, this would call the actual extraction pipeline:
            #   from services.bedrock import extract_document_fields
            #   extracted = extract_document_fields(pdf_path.read_bytes())
            #
            # For now, we provide the harness structure. Uncomment and implement
            # when real Form 16 samples are available.
            extracted: dict = {}  # Placeholder — replace with actual extraction

            for field in TARGET_FIELDS:
                if field not in expected:
                    continue
                field_total[field] += 1
                if values_match(extracted.get(field), expected[field]):
                    field_correct[field] += 1

        # Report results
        print("\n" + "=" * 60)
        print("EXTRACTION ACCURACY REPORT")
        print("=" * 60)

        all_pass = True
        for field in TARGET_FIELDS:
            total = field_total[field]
            if total == 0:
                print(f"  {field:25s}  — no samples")
                continue
            accuracy = field_correct[field] / total
            status = "✓" if accuracy >= ACCURACY_THRESHOLD else "✗"
            print(f"  {field:25s}  {accuracy:6.1%}  ({field_correct[field]}/{total})  {status}")
            if accuracy < ACCURACY_THRESHOLD:
                all_pass = False

        print("=" * 60)

        assert all_pass, (
            f"One or more fields fell below the {ACCURACY_THRESHOLD:.0%} accuracy threshold. "
            "Review extraction logic and prompt engineering before proceeding."
        )

    def test_ground_truth_schema(self):
        """Verify ground_truth.json has the expected structure."""
        if not GROUND_TRUTH_FILE.exists():
            pytest.skip("ground_truth.json not found")

        gt = load_ground_truth()
        assert isinstance(gt, dict), "Ground truth must be a JSON object"

        for filename, fields in gt.items():
            assert isinstance(fields, dict), f"Entry for {filename} must be a dict"
            # At least one target field should be present
            has_target = any(f in fields for f in TARGET_FIELDS)
            assert has_target, f"Entry for {filename} must have at least one target field"
