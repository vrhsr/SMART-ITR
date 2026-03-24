import pytest
from unittest.mock import MagicMock, patch

from services.exporter import generate_excel_export, generate_itd_json
from models import Document, Client

@pytest.fixture
def sample_doc():
    doc = Document(id="test_doc", firm_id="test_firm")
    doc.extracted_data = {
        "form16": {
            "gross_salary_paise": 150000000
        }
    }
    doc.tax_computation = {
        "old_regime_tax_paise": 100000,
        "new_regime_tax_paise": 50000,
        "recommended_regime": "new",
        "savings_paise": 50000,
        "income_data_used": {
            "total_income_paise": 150000000,
            "deductions": {"80C_paise": 15000000}
        }
    }
    return doc

@pytest.fixture
def sample_client():
    return Client(id="test_client", full_name="John Doe", pan_last4="1234")


@patch('services.exporter._save_artifact')
def test_generate_excel_export(mock_save, sample_doc, sample_client):
    mock_db = MagicMock()
    generate_excel_export(sample_doc, sample_client, mock_db)
    
    assert mock_save.called
    args, kwargs = mock_save.call_args
    assert args[3] == "excel" # artifact type
    assert args[5] == "xlsx" # file extension
    assert len(args[4]) > 100 # Excel byte stream exists


@patch('services.exporter._save_artifact')
def test_generate_itd_json(mock_save, sample_doc, sample_client):
    mock_db = MagicMock()
    generate_itd_json(sample_doc, sample_client, mock_db)
    
    assert mock_save.called
    args, kwargs = mock_save.call_args
    assert args[3] == "itdx_json" 
    assert args[5] == "json"
    
    # Verify the JSON bytes are actually valid JSON and have the right root schema
    import json
    parsed = json.loads(args[4].decode("utf-8"))
    
    assert "ITR" in parsed
    assert "ITR1" in parsed["ITR"]
    assert parsed["ITR"]["ITR1"]["PersonalInfo"]["PAN"] == "XXXXX1234X"
    assert parsed["ITR"]["ITR1"]["ITR1_IncomeDeductions"]["GrossSalary"] == 1500000
