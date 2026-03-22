import asyncio
import os
import uuid
from pathlib import Path

import boto3
from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

from db import SessionLocal
from models import Firm, Client, Document
from agents.pipeline import run_document_pipeline

s3_client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))
BUCKET = os.getenv("S3_BUCKET_NAME", "smartitr-docs")

def run_test():
    filepath = Path("tests/data/form16/1_Form16_Sample.pdf")
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return

    db = SessionLocal()
    try:
        # Get or create a Firm
        firm = db.scalar(select(Firm).limit(1))
        if not firm:
            firm = Firm(firm_id=str(uuid.uuid4()), name="Test CA Firm")
            db.add(firm)
            db.commit()

        # Get or create a Client
        client = db.scalar(select(Client).where(Client.firm_id == firm.firm_id).limit(1))
        if not client:
            client = Client(id=str(uuid.uuid4()), firm_id=firm.firm_id, full_name="Test Client", pan_last4="1234")
            db.add(client)
            db.commit()

        doc_id = str(uuid.uuid4())
        s3_key = f"{str(firm.firm_id)}/{str(client.id)}/{doc_id}/1_Form16_Sample.pdf"

        print(f"Uploading {filepath} to s3://{BUCKET}/{s3_key} ...")
        
        # Ensure bucket exists or create it for testing (if dev)
        try:
            s3_client.head_bucket(Bucket=BUCKET)
        except Exception:
            print(f"Bucket {BUCKET} not found or no access. Please ensure credentials in .env are correct and bucket exists.")
            # return

        with open(filepath, "rb") as f:
            pdf_bytes = f.read()
        
        # Upload using our service method
        s3_client.put_object(
            Bucket=BUCKET, 
            Key=s3_key, 
            Body=pdf_bytes, 
            ContentType="application/pdf",
            ServerSideEncryption="aws:kms"
        )
        
        print("Upload successful. Creating document record...")
        
        doc = Document(
            id=doc_id,
            firm_id=firm.firm_id,
            client_id=client.id,
            document_type="Form16",
            filename="1_Form16_Sample.pdf",
            content_type="application/pdf",
            s3_bucket=BUCKET,
            s3_key=s3_key,
            status="uploaded"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        print(f"Triggering LangGraph pipeline for document {doc_id} ...")
        # Run the pipeline
        final_state = run_document_pipeline(document_id=doc_id, firm_id=str(firm.firm_id), s3_key=s3_key)
        
        print("\n=== PIPELINE COMPLETED ===")
        print(f"Status: {final_state.status}")
        if final_state.error:
            print(f"Error: {final_state.error}")
        
        db.refresh(doc)
        print("\n--- Extracted Data ---")
        import json
        print(json.dumps(doc.extracted_data, indent=2))
        
        print("\n--- Tax Computation ---")
        print(json.dumps(doc.tax_computation, indent=2))
        
        print("\n--- Validation Findings ---")
        Findings = getattr(final_state, "validation_findings", [])
        print(json.dumps(Findings, indent=2))

    finally:
        db.close()

if __name__ == "__main__":
    run_test()
