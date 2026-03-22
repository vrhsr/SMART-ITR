from __future__ import annotations

from typing import Any

def map_extracted_fields_to_income_data(extracted_fields: dict[str, Any]) -> dict[str, Any]:
    """
    Map raw extracted fields from various documents into the strictly typed
    `income_data` dictionary required by the tax_calculator engine.
    
    This function handles precedence (e.g., AIS salary figure > Form 16 salary figure)
    and formatting.
    """
    
    form16 = extracted_fields.get("form16", {})
    bank = extracted_fields.get("bank_statement", {})
    ais = extracted_fields.get("ais", {})
    
    # 1. Salary (Priority: AIS > Form 16 > Bank)
    # The tax engine standard deduction logic is inside old/new regime calculators.
    # Therefore, we pass Gross Salary.
    salary_paise = ais.get("salary_as_reported_paise") or form16.get("gross_salary_paise") or bank.get("probable_salary_credits_paise") or 0
    
    # 2. Interest / Other Sources
    interest_paise = ais.get("interest_as_reported_paise") or bank.get("probable_interest_income_paise") or 0
    dividend_paise = ais.get("dividend_as_reported_paise") or 0
    
    total_income_paise = salary_paise + interest_paise + dividend_paise
    
    # 3. Deductions (From Form 16 Chapter VI-A)
    f16_deductions = form16.get("deductions_chapter_via", {})
    deductions = {
        "80C_paise": f16_deductions.get("section_80C_paise", 0),
        "80D_paise": f16_deductions.get("section_80D_paise", 0),
        "80E_paise": f16_deductions.get("section_80E_paise", 0),
        "hra_exemption_paise": 0, # usually handled within Form 16 gross salary derivation, omitting here for simplicity unless explicitly parsed
        "lta_exemption_paise": 0,
    }
    
    return {
        "total_income_paise": total_income_paise,
        "is_salaried": salary_paise > 0,
        "age_years": 30,  # Defaulting to 30 as birthdate extraction is complex and fragile. The CA will override in dashboard if senior citizen.
        "deductions": deductions,
    }
