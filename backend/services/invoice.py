from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from core.settings import settings
from models import Firm
from services.s3 import put_encrypted_object


def _generate_invoice_pdf_bytes(*, firm: Firm, amount_inr: int, gst_rate_percent: int = 18) -> bytes:
  buffer = BytesIO()
  c = canvas.Canvas(buffer, pagesize=A4)
  c.setFont("Helvetica-Bold", 14)
  c.drawString(50, 800, "SmartITR Invoice")

  c.setFont("Helvetica", 10)
  c.drawString(50, 780, f"Firm: {firm.name}")
  c.drawString(50, 765, f"Plan: {firm.subscription_plan}")

  taxable = amount_inr
  gst = (taxable * gst_rate_percent) // 100
  total = taxable + gst

  c.drawString(50, 740, f"Amount (excl. GST): ₹{taxable}")
  c.drawString(50, 725, f"GST @ {gst_rate_percent}%: ₹{gst}")
  c.drawString(50, 710, f"Total: ₹{total}")

  c.drawString(50, 690, f"Issue date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
  c.showPage()
  c.save()
  return buffer.getvalue()


def store_invoice_pdf(*, firm: Firm, amount_inr: int) -> str:
  """
  Generate and upload a GST invoice PDF to S3.
  Returns the S3 key.
  """

  pdf_bytes = _generate_invoice_pdf_bytes(firm=firm, amount_inr=amount_inr)
  bucket = f"smartitr-billing-{settings.aws_region}"
  key = f"invoices/{firm.firm_id}/{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.pdf"
  put_encrypted_object(bucket=bucket, key=key, data=pdf_bytes, kms_key_id="alias/smartitr-billing")
  return key

