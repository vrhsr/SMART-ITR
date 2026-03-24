import pytest
from engine.tax_calculator import compare_regimes, calculate_tax_liability_paise, _rupees_to_paise

def test_tax_calculator_basic():
    # Salaried, income 12L
    # SD (Old): 50k. Taxable: 11.5L. Slabs: 12.5k (2.5-5) + 100k (5-10) + 45k (10-11.5) = 157,500.
    # Cess: 6,300. Total: 163,800.
    
    # SD (New): 75k. Taxable: 11.25L. Slab: < 12L => 0.
    
    data = {"total_income_paise": 1_200_000 * 100, "is_salaried": True}
    res = compare_regimes(data)
    assert res["new_tax"] == 0
    assert res["old_tax"] == 163_800 * 100
    assert res["recommended_regime"] == "new"

def test_negative_income_rejected():
    with pytest.raises(ValueError):
        calculate_tax_liability_paise(taxable_income_paise=-100)

def test_old_regime_exemption_limits():
    data_senior = {"total_income_paise": 300_000 * 100, "is_salaried": False, "age_years": 65}
    res_senior = compare_regimes(data_senior)
    assert res_senior["old_tax"] == 0
    
    data_super = {"total_income_paise": 500_000 * 100, "is_salaried": False, "age_years": 85}
    res_super = compare_regimes(data_super)
    assert res_super["old_tax"] == 0

def test_old_regime_max_80c_cap_applied():
    # Income 10L, 80C 2L (capped at 1.5L)
    # Taxable: 10L - 1.5L = 8.5L.
    # Slabs: 12,500 (2.5-5L) + 70,000 (20% of 3.5L) = 82,500.
    # Cess: 3,300. Total = 85,800.
    data = {"total_income_paise": 1_000_000 * 100, "is_salaried": False, "deductions": {"80C_paise": 200_000 * 100}}
    res = compare_regimes(data)
    assert res["deductions_applied"]["80C_paise"] == 150_000 * 100
    assert res["old_tax"] == 85_800 * 100

@pytest.mark.parametrize(
    "income, ded_80c, age, expected_old_paise, expected_new_paise, expected_rec, expected_savings_paise",
    [
        # Old Regime tests
        (600_000, 150_000, 30, 0, 0, "old", 0), 
        (1_200_000, 0, 30, 163_800 * 100, 0, "new", 163_800 * 100),
        (1_200_001, 150_000, 30, 117_00031, 0, "new", 117_00031), 
        (15_000_000, 150_000, 30, 508_599_000, 498_433_000, "new", 10_166_000), 

        # Senior Citizens
        (600_000, 0, 65, 20_800 * 100, 0, "new", 20_800 * 100), 
        (600_000, 0, 85, 10_400 * 100, 0, "new", 10_400 * 100), 
        
        # Zeroes
        (0, 0, 30, 0, 0, "old", 0),
        (10_000, 0, 30, 0, 0, "old", 0),
    ]
)
def test_compare_regimes_extensive(income, ded_80c, age, expected_old_paise, expected_new_paise, expected_rec, expected_savings_paise):
    data = {"total_income_paise": income * 100, "is_salaried": True, "age_years": age, "deductions": {"80C_paise": ded_80c * 100}}
    res = compare_regimes(data)
    assert res["old_tax"] == expected_old_paise
    assert res["new_tax"] == expected_new_paise
    assert res["recommended_regime"] == expected_rec
    assert res["savings"] == expected_savings_paise
