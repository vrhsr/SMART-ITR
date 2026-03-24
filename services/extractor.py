from __future__ import annotations

import json
import logging
from typing import Any
from dataclasses import dataclass

from services.bedrock import _invoke_bedrock

logger = logging.getLogger("smartitr")

# We use Haiku for fast, cheap, structural extraction
HAIKU_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

@dataclass
class ExtractionResult:
    data: dict[str, Any]
    confidence: float
    raw_response: str


def _clean_json_response(response_text: str) -> dict[str, Any]:
    """Helper to parse JSON from Claude response, handling markdown blocks."""
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    text = text.strip()
    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON: {e}. Raw text: {text[:200]}")
        return {}


def _field_confidence(data: dict, required_keys: list[str]) -> float:
    """Calculate confidence based on how many required keys have non-zero values."""
    if not data:
        return 0.0
    populated = sum(1 for k in required_keys if data.get(k))
    return round(min(0.98, populated / len(required_keys)), 2)


def extract_form16_fields(*, raw_text: str, tables: dict[str, Any]) -> ExtractionResult:
    """
    Extract structured fields from Form 16 text and tables.

    Form 16 is issued by employer and has two parts:
    - Part A: TDS certificate with employer/employee details and TDS summary
    - Part B: Detailed salary breakup and Chapter VI-A deductions
    """
    prompt = f"""You are an expert Indian Chartered Accountant AI specializing in Form 16 analysis.
Analyze the following Form 16 document text carefully. Form 16 has two parts:
- Part A: Issued by employer, contains TAN, employer address, TDS quarters, total TDS deposited
- Part B: Salary breakdown — Basic, HRA, Special Allowance, Other Allowances, gross salary, deductions under Chapter VI-A

CRITICAL RULES:
1. Output ONLY a valid JSON object. No markdown, no explanation, no preamble.
2. ALL monetary amounts MUST be integers in PAISE (1 rupee = 100 paise). Multiply rupees by 100.
3. If a field is genuinely not found in the document, use 0 for amounts and empty string "" for text.
4. Do NOT guess amounts — if not visible, return 0.
5. PAN format is like ABCDE1234F (10 characters). TAN format is like ABCD12345E.
6. For assessment year, use format "2025-26" (the year the return is filed).

OUTPUT JSON SCHEMA (do not add or remove keys):
{{
    "employer_name": "string — legal name of employer",
    "employer_tan": "string — employer's TAN number",
    "employee_pan": "string — employee's PAN number",
    "employee_name": "string — full name of employee",
    "assessment_year": "string — e.g., 2025-26",
    "financial_year": "string — e.g., 2024-25",
    "gross_salary_paise": 0,
    "basic_salary_paise": 0,
    "hra_received_paise": 0,
    "special_allowance_paise": 0,
    "lta_paise": 0,
    "other_allowances_paise": 0,
    "standard_deduction_paise": 0,
    "professional_tax_paise": 0,
    "net_taxable_salary_paise": 0,
    "tds_deducted_paise": 0,
    "deductions_chapter_via": {{
        "section_80C_paise": 0,
        "section_80CCD1B_paise": 0,
        "section_80D_paise": 0,
        "section_80E_paise": 0,
        "section_80G_paise": 0,
        "total_chapter_via_paise": 0
    }},
    "hra_exemption_80GG_paise": 0
}}

FORM 16 DOCUMENT TEXT:
{raw_text[:10000]}

TABLE DATA (if any):
{json.dumps(tables, indent=2)[:3000] if tables else "No table data"}
"""

    try:
        response_text = _invoke_bedrock(model_id=HAIKU_MODEL_ID, prompt=prompt)
        data = _clean_json_response(response_text)

        required = ["gross_salary_paise", "net_taxable_salary_paise", "tds_deducted_paise", "employer_name", "assessment_year"]
        confidence = _field_confidence(data, required)

        # Derived sanity check: gross should be >= net
        gross = data.get("gross_salary_paise", 0)
        net = data.get("net_taxable_salary_paise", 0)
        if gross > 0 and net > gross:
            logger.warning("Form 16: net_taxable_salary > gross_salary, possible extraction error")
            confidence = max(0.0, confidence - 0.15)

        # Never log PII fields
        safe_log = {k: v for k, v in data.items() if k not in ("employee_pan", "employer_tan", "employee_name")}
        logger.info(f"Form 16 extraction successful (confidence={confidence}): {safe_log}")

        return ExtractionResult(data=data, confidence=confidence, raw_response=response_text)
    except Exception as e:
        logger.error(f"Form 16 extraction failed: {e}")
        return ExtractionResult(data={}, confidence=0.0, raw_response="")


def extract_bank_statement_transactions(*, raw_text: str) -> ExtractionResult:
    """
    Extract aggregated transaction summary from a bank statement.
    Identifies salary credits, interest income, recurring debits.
    """
    prompt = f"""You are an expert Indian Chartered Accountant AI analyzing a bank statement.

Analyze the bank statement and extract a structured financial summary. Focus on:
- Regular monthly credits around same date/amount (likely salary)
- Small regular credits labeled as "INT CREDIT" or "INTEREST" (interest income)
- Mutual fund redemptions or equity credits (capital gains clue)

CRITICAL RULES:
1. Output ONLY a valid JSON object.
2. ALL amounts MUST be integers in PAISE (1 rupee = 100 paise). Multiply rupees by 100.
3. If not clearly identifiable, set value to 0.
4. total_credits_paise = sum of all credit entries in the statement period.

OUTPUT JSON SCHEMA:
{{
    "statement_period_from": "string — e.g., 2024-04-01",
    "statement_period_to": "string — e.g., 2025-03-31",
    "total_credits_paise": 0,
    "total_debits_paise": 0,
    "probable_salary_credits_paise": 0,
    "probable_interest_income_paise": 0,
    "probable_capital_gains_credits_paise": 0,
    "probable_rental_income_paise": 0,
    "total_transactions": 0
}}

BANK STATEMENT TEXT:
{raw_text[:14000]}
"""

    try:
        response_text = _invoke_bedrock(model_id=HAIKU_MODEL_ID, prompt=prompt)
        data = _clean_json_response(response_text)

        required = ["total_credits_paise", "probable_salary_credits_paise", "total_debits_paise"]
        confidence = _field_confidence(data, required)

        return ExtractionResult(data=data, confidence=confidence, raw_response=response_text)
    except Exception as e:
        logger.error(f"Bank statement extraction failed: {e}")
        return ExtractionResult(data={}, confidence=0.0, raw_response="")


def extract_ais_entries(*, raw_text: str) -> ExtractionResult:
    """
    Extract aggregated income entries from AIS (Annual Information Statement) / Form 26AS.
    AIS is the gold standard — it receives data from employers, banks, mutual funds directly.
    """
    prompt = f"""You are an expert Indian Chartered Accountant AI analyzing an AIS (Annual Information Statement) or Form 26AS.

AIS is issued by the Income Tax Department and aggregates all financial information reported by third parties about the taxpayer:
- Salary reported by employer (Part B of Form 26AS or Section A of AIS)
- Interest reported by bank (Part C of Form 26AS or Section B of AIS)
- Dividend reported by companies
- TDS deducted and deposited across all deductors

CRITICAL RULES:
1. Output ONLY a valid JSON object.
2. ALL amounts MUST be integers in PAISE (1 rupee = 100 paise). Multiply rupees by 100.
3. AIS figures are REPORTED amounts — use them as the most authoritative source.
4. tds_as_per_ais_paise = total TDS deposited across ALL employers/banks/other deductors.

OUTPUT JSON SCHEMA:
{{
    "assessment_year": "string — e.g., 2025-26",
    "salary_as_reported_paise": 0,
    "interest_from_savings_paise": 0,
    "interest_from_deposits_paise": 0,
    "interest_as_reported_paise": 0,
    "dividend_as_reported_paise": 0,
    "tds_as_per_ais_paise": 0,
    "mutual_fund_sales_paise": 0,
    "equity_sales_paise": 0,
    "other_income_as_reported_paise": 0
}}

AIS / FORM 26AS TEXT:
{raw_text[:14000]}
"""

    try:
        response_text = _invoke_bedrock(model_id=HAIKU_MODEL_ID, prompt=prompt)
        data = _clean_json_response(response_text)

        required = ["salary_as_reported_paise", "tds_as_per_ais_paise", "interest_as_reported_paise"]
        confidence = _field_confidence(data, required)

        return ExtractionResult(data=data, confidence=confidence, raw_response=response_text)
    except Exception as e:
        logger.error(f"AIS extraction failed: {e}")
        return ExtractionResult(data={}, confidence=0.0, raw_response="")
