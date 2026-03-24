from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timezone

import xlsxwriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from sqlalchemy.orm import Session

from core.settings import settings
from models import Client, Document, ExportArtifact
from services.s3 import put_encrypted_object


def _save_artifact(db: Session, doc: Document, client: Client, artifact_type: str, bytes_data: bytes, ext: str) -> None:
    bucket = f"smartitr-exports-{settings.aws_region}"
    key = f"firms/{doc.firm_id}/clients/{client.id}/documents/{doc.id}/{artifact_type}_{uuid.uuid4().hex[:8]}.{ext}"
    
    put_encrypted_object(bucket=bucket, key=key, data=bytes_data, kms_key_id="alias/smartitr-exports")
    
    # Check if artifact exists, update if it does
    from sqlalchemy import select
    existing = db.scalar(
        select(ExportArtifact).where(
            ExportArtifact.document_id == doc.id,
            ExportArtifact.artifact_type == artifact_type
        )
    )
    
    if existing:
        existing.s3_bucket = bucket
        existing.s3_key = key
    else:
        artifact = ExportArtifact(
            firm_id=doc.firm_id,
            document_id=doc.id,
            artifact_type=artifact_type,
            s3_bucket=bucket,
            s3_key=key
        )
        db.add(artifact)
    db.commit()


def generate_excel_export(doc: Document, client: Client, db: Session) -> None:
    """Generates an Excel document optimized for Winman/CompuTax import."""
    
    extracted = doc.extracted_data or {}
    tax = doc.tax_computation or {}
    income_data = tax.get("income_data_used", {})
    deductions = income_data.get("deductions", {})
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # --- Sheet 1: Winman/CompuTax Standard Import (Horizontal) ---
    ws_import = workbook.add_worksheet("Tax Software Import")
    
    # Styles
    header_format = workbook.add_format({
        'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center', 'valign': 'vcenter'
    })
    money_format = workbook.add_format({'num_format': '0', 'border': 1})
    text_format = workbook.add_format({'border': 1})
    
    # Standard Indian Tax Software Import Headers
    headers = [
        "PAN",
        "FirstName",
        "LastName",
        "EmployerName",
        "EmployerTAN",
        "GrossSalary_17_1",
        "ValuePerquisites_17_2",
        "ProfitInLieu_17_3",
        "ExemptAllowances_10",
        "StandardDeduction_16_ia",
        "ProfessionalTax_16_iii",
        "TotalIncomeFromSalary",
        "TDS_Deducted",
        "80C_LIC_PPF",
        "80CCC_Pension",
        "80CCD1B_NPS",
        "80D_Medical",
        "80TTA_Interest",
        "TotalChapterVIA"
    ]
    
    # Write Headers
    for col_num, header_title in enumerate(headers):
        ws_import.write(0, col_num, header_title, header_format)
        ws_import.set_column(col_num, col_num, 20)
        
    # Extract values safely
    def get_money(field: str) -> int:
        return int(extracted.get(field, 0) or 0)
        
    def split_name(full_name: str) -> tuple[str, str]:
        parts = str(full_name or "").strip().split(" ", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return parts[0] if parts else "", ""
        
    first_name, last_name = split_name(client.full_name)
    pan = f"XXXXX{client.pan_last4}X" if client.pan_last4 else ""
    
    gross_17_1 = get_money("gross_salary")
    perquisites = get_money("value_of_perquisites")
    profit_in_lieu = get_money("profit_in_lieu_of_salary")
    exempt_allowances = get_money("exempt_allowances")
    std_deduction = get_money("standard_deduction")
    prof_tax = get_money("professional_tax")
    
    salary_income = gross_17_1 + perquisites + profit_in_lieu - exempt_allowances - std_deduction - prof_tax
    
    sec_80c = int(deductions.get("80c_paise", 0) / 100)
    sec_80ccc = int(deductions.get("80ccc_paise", 0) / 100)
    sec_80ccd1b = int(deductions.get("80ccd1b_paise", 0) / 100)
    sec_80d = int(deductions.get("80d_paise", 0) / 100)
    sec_80tta = int(deductions.get("80tta_paise", 0) / 100)
    total_deductions = sec_80c + sec_80ccc + sec_80ccd1b + sec_80d + sec_80tta
    
    # Write Data Row
    data_row = [
        pan,
        first_name,
        last_name,
        str(extracted.get("employer_name", "")),
        str(extracted.get("employer_tan", "")),
        gross_17_1,
        perquisites,
        profit_in_lieu,
        exempt_allowances,
        std_deduction,
        prof_tax,
        max(0, salary_income),
        get_money("tds_deducted"),
        sec_80c,
        sec_80ccc,
        sec_80ccd1b,
        sec_80d,
        sec_80tta,
        total_deductions
    ]
    
    for col_num, cell_value in enumerate(data_row):
        fmt = money_format if isinstance(cell_value, (int, float)) else text_format
        ws_import.write(1, col_num, cell_value, fmt)

    # --- Sheet 2: SmartITR Audit Trail ---
    ws_audit = workbook.add_worksheet("AI Audit & Adjustments")
    ws_audit.set_column("A:A", 30)
    ws_audit.set_column("B:B", 25)
    ws_audit.set_column("C:C", 20)
    
    ws_audit.write("A1", "SmartITR Extraction Log", header_format)
    ws_audit.write("A3", "Field", bold := workbook.add_format({'bold': True}))
    ws_audit.write("B3", "Extracted Value", bold)
    ws_audit.write("C3", "AI Confidence", bold)
    
    row = 3
    for k, v in extracted.items():
        if not k.startswith("_"):
            conf_key = f"_confidence_{k}"
            confidence = extracted.get(conf_key, "N/A")
            
            ws_audit.write(row, 0, k)
            ws_audit.write(row, 1, str(v))
            if isinstance(confidence, float):
                ws_audit.write(row, 2, confidence, workbook.add_format({'num_format': '0.0%'}))
            else:
                ws_audit.write(row, 2, confidence)
            row += 1

    workbook.close()
    
    _save_artifact(db, doc, client, "excel", output.getvalue(), "xlsx")


def generate_itd_json(doc: Document, client: Client, db: Session) -> None:
    """Generates the official structured JSON required by the Income Tax Department portal."""
    
    # Note: A real schema is thousands of lines long. 
    # This generates a mathematically valid skeletal stub for AY 2025-26.
    
    extracted = doc.extracted_data or {}
    tax = doc.tax_computation or {}
    income_data = tax.get("income_data_used", {})
    deductions = income_data.get("deductions", {})
    
    schema = {
        "ITR": {
            "ITR1": {
                "CreationInfo": {
                    "SWVersionNo": "1.0",
                    "SWCreatedBy": "SmartITR",
                    "XMLCreatedBy": "SmartITR",
                    "XMLCreationDate": datetime.now().strftime("%Y-%m-%d"),
                    "IntermediaryCity": "",
                    "Digest": "",
                },
                "Form_ITR1": {
                    "FormName": "ITR-1",
                    "Description": "For Individuals having Income from Salary, one house property, other sources (Interest etc.) and having total income upto Rs.50 Lakh",
                    "AssessmentYear": "2025",
                    "SchemaVer": "1.0",
                },
                "PersonalInfo": {
                    "AssesseeName": {"FirstName": client.full_name, "SurName": ""},
                    "PAN": f"XXXXX{client.pan_last4}X" if client.pan_last4 else "XXXXXXXXXX",
                },
                "FilingStatus": {
                    "ReturnFileSec": "139(1)",
                    "OptOutNewRegime": "N" if tax.get("recommended_regime") == "new" else "Y"
                },
                "ITR1_IncomeDeductions": {
                    "GrossSalary": income_data.get("total_income_paise", 0) // 100,
                    "TotalDeductions": sum(deductions.values()) // 100,
                    "TotalIncome": (income_data.get("total_income_paise", 0) - sum(deductions.values())) // 100
                },
                "ITR1_TaxComputation": {
                    "TotalTaxPayable": tax.get(f"{tax.get('recommended_regime', 'new')}_regime_tax_paise", 0) // 100
                }
            }
        }
    }
    
    json_bytes = json.dumps(schema, indent=2).encode('utf-8')
    _save_artifact(db, doc, client, "itdx_json", json_bytes, "json")


def generate_client_pdf_report(doc: Document, client: Client, db: Session) -> None:
    """Generates a CA-branded PDF report for the end-user."""
    
    buffer = io.BytesIO()
    p = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    
    elements = []
    
    elements.append(Paragraph(f"Tax Computation Summary: {client.full_name}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    tax = doc.tax_computation or {}
    rec = tax.get('recommended_regime', 'unknown').upper()
    savings = tax.get('savings_paise', 0) // 100
    
    elements.append(Paragraph(f"<b>Recommended Regime:</b> {rec} REGIME", styles['Normal']))
    
    if savings > 0:
         elements.append(Paragraph(f"<b>Tax Savings vs Alternative Regime:</b> ₹{savings:,}", styles['Normal']))
         
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"<b>Old Regime Tax:</b> ₹{tax.get('old_regime_tax_paise', 0) // 100:,}", styles['Normal']))
    elements.append(Paragraph(f"<b>New Regime Tax:</b> ₹{tax.get('new_regime_tax_paise', 0) // 100:,}", styles['Normal']))

    p.build(elements)
    
    _save_artifact(db, doc, client, "client_report_pdf", buffer.getvalue(), "pdf")

