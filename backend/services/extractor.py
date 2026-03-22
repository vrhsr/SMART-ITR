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
    if text.startswith("```json"):
        text = text.split("```json")[1]
    if text.startswith("```"):
        text = text.split("```")[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    
    text = text.strip()
    try:
        return json.loads(text)
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON: {e}. Raw text: {text[:200]}")
        return {}


def extract_form16_fields(*, raw_text: str, tables: dict[str, Any]) -> ExtractionResult:
    """
    Extract structured fields from Form 16 text and tables.
    """
    prompt = """
    You are an expert Indian Chartered Accountant AI. Extract the required fields from the provided Form 16 text and tables.
    
    CRITICAL RULES:
    1. Output ONLY a valid JSON object. No markdown formatting, no explanations.
    2. All amounts MUST be converted to integers representing PAISE (multiply rupees by 100).
    3. If a field is missing, set its value to 0 for amounts, or null/empty string for text.
    
    REQUIRED JSON SCHEMA:
    {
        "employer_name": "string",
        "employer_tan": "string",
        "employee_pan": "string",
        "gross_salary_paise": 0,
        "standard_deduction_paise": 0,
        "professional_tax_paise": 0,
        "net_taxable_salary_paise": 0,
        "tds_deducted_paise": 0,
        "deductions_chapter_via": {
            "section_80C_paise": 0,
            "section_80D_paise": 0,
            "section_80E_paise": 0
        },
        "assessment_year": "string (e.g., 2024-25)"
    }
    
    DOCUMENT TEXT:
    """ + raw_text[:8000]

    try:
        response_text = _invoke_bedrock(model_id=HAIKU_MODEL_ID, prompt=prompt)
        data = _clean_json_response(response_text)
        
        # Calculate a basic confidence score based on how many fields were successfully populated
        fields_found = sum(1 for v in data.values() if v)
        confidence = min(0.95, fields_found / len(data.keys())) if data else 0.0
        
        # Avoid logging PII like PAN
        safe_log = {k: v for k, v in data.items() if k not in ("employee_pan", "employer_tan")}
        logger.info(f"Form 16 extraction successful: {safe_log}")
        
        return ExtractionResult(data=data, confidence=confidence, raw_response=response_text)
    except Exception as e:
        logger.error(f"Form 16 extraction failed: {e}")
        return ExtractionResult(data={}, confidence=0.0, raw_response="")


def extract_bank_statement_transactions(*, raw_text: str) -> ExtractionResult:
    """
    Extract aggregated transaction data from a bank statement.
    """
    prompt = """
    You are an expert Indian Chartered Accountant AI. Analyze this bank statement and extract aggregated totals.
    
    CRITICAL RULES:
    1. Output ONLY a valid JSON object. No markdown formatting, no explanations.
    2. All amounts MUST be converted to integers representing PAISE (multiply rupees by 100).
    
    REQUIRED JSON SCHEMA:
    {
        "total_credits_paise": 0,
        "total_debits_paise": 0,
        "probable_salary_credits_paise": 0,
        "probable_interest_income_paise": 0,
        "total_transactions": 0
    }
    
    DOCUMENT TEXT:
    """ + raw_text[:12000]

    try:
        response_text = _invoke_bedrock(model_id=HAIKU_MODEL_ID, prompt=prompt)
        data = _clean_json_response(response_text)
        confidence = 0.85 if data else 0.0
        return ExtractionResult(data=data, confidence=confidence, raw_response=response_text)
    except Exception as e:
        logger.error(f"Bank statement extraction failed: {e}")
        return ExtractionResult(data={}, confidence=0.0, raw_response="")


def extract_ais_entries(*, raw_text: str) -> ExtractionResult:
    """
    Extract aggregated entries from AIS (Annual Information Statement) / Form 26AS.
    """
    prompt = """
    You are an expert Indian Chartered Accountant AI. Analyze this AIS/Form 26AS document and extract the reported totals.
    
    CRITICAL RULES:
    1. Output ONLY a valid JSON object. No markdown formatting, no explanations.
    2. All amounts MUST be converted to integers representing PAISE (multiply rupees by 100).
    
    REQUIRED JSON SCHEMA:
    {
        "salary_as_reported_paise": 0,
        "interest_as_reported_paise": 0,
        "dividend_as_reported_paise": 0,
        "tds_as_per_ais_paise": 0,
        "mutual_fund_sales_paise": 0,
        "equity_sales_paise": 0
    }
    
    DOCUMENT TEXT:
    """ + raw_text[:12000]

    try:
        response_text = _invoke_bedrock(model_id=HAIKU_MODEL_ID, prompt=prompt)
        data = _clean_json_response(response_text)
        confidence = 0.90 if data else 0.0
        return ExtractionResult(data=data, confidence=confidence, raw_response=response_text)
    except Exception as e:
        logger.error(f"AIS extraction failed: {e}")
        return ExtractionResult(data={}, confidence=0.0, raw_response="")

