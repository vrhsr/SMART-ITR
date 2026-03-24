import pytest

from engine.field_mapper import map_extracted_fields_to_income_data

def test_map_empty_fields():
    data = map_extracted_fields_to_income_data({})
    assert data["total_income_paise"] == 0
    assert data["is_salaried"] is False
    assert data["deductions"]["80C_paise"] == 0


def test_map_ais_priority_over_form16():
    # AIS reports 15L, Form 16 reports 12L. Expected: 15L.
    extracted = {
        "form16": {
            "gross_salary_paise": 120000000,
            "deductions_chapter_via": {
                "section_80C_paise": 15000000
            }
        },
        "ais": {
            "salary_as_reported_paise": 150000000,
            "interest_as_reported_paise": 1000000
        }
    }
    
    data = map_extracted_fields_to_income_data(extracted)
    
    assert data["total_income_paise"] == 151000000 # 15L salary + 10k interest
    assert data["is_salaried"] is True
    assert data["deductions"]["80C_paise"] == 15000000 # Deductions still pulled from Form 16


def test_map_form16_fallback():
    extracted = {
        "form16": {
            "gross_salary_paise": 120000000,
        }
    }
    
    data = map_extracted_fields_to_income_data(extracted)
    
    assert data["total_income_paise"] == 120000000
    assert data["is_salaried"] is True
