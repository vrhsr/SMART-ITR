import os
import sys
import json
import boto3
from dotenv import load_dotenv

# Add backend to path to import services
sys.path.append(os.getcwd())

from services.textract import textract_detect_text, textract_analyze_tables
from services.extractor import extract_form16_fields

def main():
    load_dotenv()
    
    pdf_path = "tests/data/form16/1_Form16_Sample.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: Sample PDF not found at {pdf_path}")
        return

    print(f"Reading {pdf_path}...")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print("Running AWS Textract...")
    raw_text = textract_detect_text(pdf_bytes=pdf_bytes)
    tables = textract_analyze_tables(pdf_bytes=pdf_bytes)

    print("Running Haiku Extraction...")
    result = extract_form16_fields(raw_text=raw_text, tables=tables)

    print("\n--- EXTRACTION RESULTS ---")
    print(json.dumps(result.data, indent=2))
    print(f"\nConfidence: {result.confidence:.2%}")

if __name__ == "__main__":
    main()
