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
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # 1. Income Summary Sheet
    ws1 = workbook.add_worksheet("Income Summary")
    ws1.set_column("A:A", 30)
    ws1.set_column("B:B", 20)
    
    bold = workbook.add_format({'bold': True})
    money = workbook.add_format({'num_format': '₹#,##0'})
    
    ws1.write("A1", "Client Name", bold)
    ws1.write("B1", client.full_name)
    ws1.write("A2", "PAN Last 4", bold)
    ws1.write("B2", client.pan_last4)
    
    ws1.write("A4", "Gross Salary", bold)
    ws1.write("B4", income_data.get("total_income_paise", 0) / 100, money)
    
    # 2. Deductions Sheet
    ws2 = workbook.add_worksheet("Deductions (Chapter VI-A)")
    ws2.set_column("A:A", 20)
    ws2.set_column("B:B", 20)
    
    deductions = income_data.get("deductions", {})
    r = 0
    for k, v in deductions.items():
        if v > 0:
            ws2.write(r, 0, k.replace("_paise", "").upper(), bold)
            ws2.write(r, 1, v / 100, money)
            r += 1

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

