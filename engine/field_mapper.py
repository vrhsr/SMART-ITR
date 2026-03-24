from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("smartitr")


def map_extracted_fields_to_income_data(extracted_fields: dict[str, Any]) -> dict[str, Any]:
    """
    Map raw extracted fields from multiple documents into the `income_data` dict
    required by the tax_calculator engine.

    Precedence rules (most authoritative source wins):
      Salary:   AIS > Form 16 > Bank statement (salary credits)
      Interest: AIS (savings + deposits) > Bank (probable interest) > 0
      Dividend: AIS > 0
      TDS:      AIS total TDS > Form 16 TDS deducted
      Deductions: Form 16 Chapter VI-A (only source)
    """

    form16 = extracted_fields.get("form16", {})
    bank = extracted_fields.get("bank_statement", {})
    ais = extracted_fields.get("ais", {})

    # ─── SALARY ────────────────────────────────────────────────────────────────
    # AIS reported salary is most authoritative (government-verified data)
    ais_salary = ais.get("salary_as_reported_paise", 0) or 0
    f16_gross = form16.get("gross_salary_paise", 0) or 0
    bank_salary = bank.get("probable_salary_credits_paise", 0) or 0

    salary_paise = ais_salary or f16_gross or bank_salary
    salary_source = "ais" if ais_salary else ("form16" if f16_gross else "bank")

    if ais_salary and f16_gross and abs(ais_salary - f16_gross) > 100_000:  # ₹1,000 mismatch
        logger.warning(
            f"Salary mismatch: AIS=₹{ais_salary//100} vs Form16=₹{f16_gross//100}. Using AIS."
        )

    # ─── INTEREST INCOME ───────────────────────────────────────────────────────
    ais_interest = (
        (ais.get("interest_from_savings_paise") or 0)
        + (ais.get("interest_from_deposits_paise") or 0)
    ) or (ais.get("interest_as_reported_paise") or 0)
    bank_interest = bank.get("probable_interest_income_paise", 0) or 0
    interest_paise = ais_interest or bank_interest

    # ─── OTHER INCOME ──────────────────────────────────────────────────────────
    dividend_paise = ais.get("dividend_as_reported_paise", 0) or 0
    other_income_paise = ais.get("other_income_as_reported_paise", 0) or 0

    # Capital gains (bank credits from equity/MF redemptions)
    capital_gains_paise = (
        (ais.get("equity_sales_paise") or 0) +
        (ais.get("mutual_fund_sales_paise") or 0)
    )

    total_gross_income_paise = salary_paise + interest_paise + dividend_paise + other_income_paise

    # ─── HRA EXEMPTION ─────────────────────────────────────────────────────────
    # Form 16 gross salary is post HRA-exemption if employer calculated it.
    # Use explicit field if extracted.
    hra_exemption_paise = form16.get("hra_exemption_80GG_paise", 0) or 0

    # ─── TDS CREDIT ────────────────────────────────────────────────────────────
    ais_tds = ais.get("tds_as_per_ais_paise", 0) or 0
    f16_tds = form16.get("tds_deducted_paise", 0) or 0
    tds_credit_paise = ais_tds or f16_tds  # AIS includes TDS from all deductors

    # ─── DEDUCTIONS (CHAPTER VI-A from Form 16) ────────────────────────────────
    f16_deductions = form16.get("deductions_chapter_via", {}) or {}
    deductions = {
        "80C_paise": f16_deductions.get("section_80C_paise", 0) or 0,
        "80CCD1B_paise": f16_deductions.get("section_80CCD1B_paise", 0) or 0,
        "80D_paise": f16_deductions.get("section_80D_paise", 0) or 0,
        "80E_paise": f16_deductions.get("section_80E_paise", 0) or 0,
        "80G_paise": f16_deductions.get("section_80G_paise", 0) or 0,
        "hra_exemption_paise": hra_exemption_paise,
        "lta_exemption_paise": form16.get("lta_paise", 0) or 0,
    }

    return {
        "total_income_paise": total_gross_income_paise,
        "salary_paise": salary_paise,
        "interest_paise": interest_paise,
        "dividend_paise": dividend_paise,
        "capital_gains_paise": capital_gains_paise,
        "tds_credit_paise": tds_credit_paise,
        "is_salaried": salary_paise > 0,
        "age_years": 30,  # CA can override in the dashboard for senior citizen cases
        "deductions": deductions,
        "_meta": {
            "salary_source": salary_source,
            "ais_tds_used": ais_tds > 0,
            "has_capital_gains": capital_gains_paise > 0,
        },
    }
