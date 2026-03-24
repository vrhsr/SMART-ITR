from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class TaxComputationResult:
    old_regime_tax_paise: int
    new_regime_tax_paise: int
    recommended_regime: str
    savings_paise: int


def _rupees_to_paise(rupees: int | float) -> int:
    return int(round(rupees * 100))


def _clamp_non_negative_paise(value: int) -> int:
    return max(0, value)


def _percent_of_paise(amount_paise: int, percent: int | float) -> int:
    return int(round((amount_paise * percent) / 100))


def _surcharge_rate(income_rupees: int, is_new_regime: bool) -> int:
    if income_rupees > 50_000_000: # 5 Cr
        return 25 if is_new_regime else 37
    if income_rupees > 20_000_000: # 2 Cr
        return 25
    if income_rupees > 10_000_000: # 1 Cr
        return 15
    if income_rupees > 5_000_000: # 50 L
        return 10
    return 0

def calculate_new_regime_tax(gross_income_paise: int) -> dict[str, int]:
    # AY 2025-26 New Regime
    std_ded = 75_000
    gross_rupees = gross_income_paise // 100
    taxable_rupees = max(0, gross_rupees - std_ded)
    
    tax_rupees = 0.0
    # Slabs: 3L@0, 3-7L@5%, 7-10L@10%, 10-12L@15%, 12-15L@20%, 15L+@30%
    if taxable_rupees > 300_000:
        tax_rupees += (min(taxable_rupees, 700_000) - 300_000) * 0.05
    if taxable_rupees > 700_000:
        tax_rupees += (min(taxable_rupees, 1_000_000) - 700_000) * 0.10
    if taxable_rupees > 1_000_000:
        tax_rupees += (min(taxable_rupees, 1_200_000) - 1_000_000) * 0.15
    if taxable_rupees > 1_200_000:
        tax_rupees += (min(taxable_rupees, 1_500_000) - 1_200_000) * 0.20
    if taxable_rupees > 1_500_000:
        tax_rupees += (taxable_rupees - 1_500_000) * 0.30
        
    tax_before_cess = _rupees_to_paise(tax_rupees)
    
    # Rebate 87A New Regime: up to 12L taxable income -> 0 tax
    if taxable_rupees <= 1_200_000:
        tax_before_cess = 0
        
    s_rate = _surcharge_rate(taxable_rupees, True)
    surcharge_paise = _percent_of_paise(tax_before_cess, s_rate)
    cess_paise = _percent_of_paise(tax_before_cess + surcharge_paise, 4)
    
    return {
        "total_tax": tax_before_cess + surcharge_paise + cess_paise,
        "tax_before_cess": tax_before_cess,
        "surcharge": surcharge_paise,
        "cess": cess_paise
    }

def calculate_old_regime_tax(income_data: dict[str, Any]) -> dict[str, Any]:
    gross_paise = int(income_data.get("total_income_paise", 0))
    if gross_paise < 0: raise ValueError("Negative income")
        
    is_salaried = bool(income_data.get("is_salaried", False))
    age = int(income_data.get("age_years", 30))
    d_80c_paise = int(income_data.get("deductions", {}).get("80C_paise", 0))
    
    std_ded = 50_000 if is_salaried else 0
    c80c_rupees = min(max(0, d_80c_paise // 100), 150_000)
    
    taxable_rupees = max(0, (gross_paise // 100) - std_ded - c80c_rupees)
    
    excl = 250_000
    if age >= 80: excl = 500_000
    elif age >= 60: excl = 300_000
    
    tax_rupees = 0.0
    # Old slabs: excl@0, excl-5L@5%, 5-10L@20%, 10L+@30%
    if taxable_rupees > excl:
        tax_rupees += (min(taxable_rupees, 500_000) - excl) * 0.05
    if taxable_rupees > 500_000:
        tax_rupees += (min(taxable_rupees, 1_000_000) - 500_000) * 0.20
    if taxable_rupees > 1_000_000:
        tax_rupees += (taxable_rupees - 1_000_000) * 0.30
        
    tax_before_cess = _rupees_to_paise(tax_rupees)
    
    # Rebate 87A Old Regime: taxable income <= 5L -> max 12.5k rebate
    if taxable_rupees <= 500_000:
        tax_before_cess = max(0, tax_before_cess - _rupees_to_paise(12_500))
        
    s_rate = _surcharge_rate(taxable_rupees, False)
    surcharge_paise = _percent_of_paise(tax_before_cess, s_rate)
    cess_paise = _percent_of_paise(tax_before_cess + surcharge_paise, 4)
    
    return {
        "total_tax": tax_before_cess + surcharge_paise + cess_paise,
        "tax_before_cess": tax_before_cess,
        "surcharge": surcharge_paise,
        "cess": cess_paise,
        "deductions_applied": {"80C_paise": _rupees_to_paise(c80c_rupees)}
    }

def compare_regimes(income_data: dict[str, Any]) -> dict[str, Any]:
    old = calculate_old_regime_tax(income_data)
    new = calculate_new_regime_tax(int(income_data.get("total_income_paise", 0)))
    
    old_tax = old["total_tax"]
    new_tax = new["total_tax"]
    
    if new_tax <= old_tax:
        rec = "new"
        savings = old_tax - new_tax
        baseline = old_tax
    else:
        rec = "old"
        savings = new_tax - old_tax
        baseline = new_tax
        
    if int(income_data.get("total_income_paise", 0)) == 0:
        rec = "old"
    elif old_tax == 0 and new_tax == 0:
        rec = "old"

    savings_percentage = 0
    if baseline > 0:
        savings_percentage = (savings * 10000) // baseline
        
    return {
        "old_tax": old_tax,
        "new_tax": new_tax,
        "recommended_regime": rec,
        "savings": savings,
        "savings_percentage": savings_percentage,
        "deductions_applied": old.get("deductions_applied", {}),
    }


def calculate_tax_liability_paise(*, taxable_income_paise: int) -> TaxComputationResult:
    if taxable_income_paise < 0: raise ValueError("Negative income")
    res = compare_regimes({"total_income_paise": taxable_income_paise, "is_salaried": True, "age_years": 30, "deductions": {}})
    return TaxComputationResult(
        old_regime_tax_paise=res["old_tax"],
        new_regime_tax_paise=res["new_tax"],
        recommended_regime=res["recommended_regime"],
        savings_paise=res["savings"]
    )
