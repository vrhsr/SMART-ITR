import pytest
from unittest.mock import patch, MagicMock

from services.extractor import extract_form16_fields, extract_bank_statement_transactions, extract_ais_entries

@patch('services.extractor._invoke_bedrock')
def test_extract_form16_success(mock_bedrock):
    mock_bedrock.return_value = '''```json
    {
        "employer_name": "Tech Corp",
        "employer_tan": "BLRT12345A",
        "employee_pan": "ABCDE1234F",
        "gross_salary_paise": 120000000,
        "standard_deduction_paise": 5000000,
        "professional_tax_paise": 240000,
        "net_taxable_salary_paise": 114760000,
        "tds_deducted_paise": 14000000,
        "deductions_chapter_via": {
            "section_80C_paise": 15000000,
            "section_80D_paise": 2500000,
            "section_80E_paise": 0
        },
        "assessment_year": "2024-25"
    }
    ```'''
    
    result = extract_form16_fields(raw_text="Test Data", tables={})
    
    assert result.confidence > 0.90
    assert result.data["employer_name"] == "Tech Corp"
    assert result.data["gross_salary_paise"] == 120000000
    assert result.data["deductions_chapter_via"]["section_80C_paise"] == 15000000


@patch('services.extractor._invoke_bedrock')
def test_extract_form16_invalid_json(mock_bedrock):
    mock_bedrock.return_value = "Sorry, I cannot parse this document. Here is some text instead."
    
    result = extract_form16_fields(raw_text="Garbage Data", tables={})
    
    assert result.confidence == 0.0
    assert result.data == {}


@patch('services.extractor._invoke_bedrock')
def test_extract_ais_entries(mock_bedrock):
    mock_bedrock.return_value = '''{
        "salary_as_reported_paise": 150000000,
        "interest_as_reported_paise": 5000000,
        "dividend_as_reported_paise": 1000000,
        "tds_as_per_ais_paise": 20000000,
        "mutual_fund_sales_paise": 0,
        "equity_sales_paise": 0
    }'''
    
    result = extract_ais_entries(raw_text="AIS Data")
    
    assert result.confidence == 0.90
    assert result.data["salary_as_reported_paise"] == 150000000
    assert result.data["interest_as_reported_paise"] == 5000000
