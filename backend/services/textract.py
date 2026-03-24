from __future__ import annotations

from typing import Any

import boto3

from core.settings import settings


def textract_detect_text(*, pdf_bytes: bytes) -> str:
    """
    Extract raw text from a PDF using AWS Textract.
    """

    client = boto3.client("textract", region_name=settings.aws_region)
    response = client.detect_document_text(Document={"Bytes": pdf_bytes})
    blocks = response.get("Blocks", []) or []
    lines: list[str] = []
    for block in blocks:
        if block.get("BlockType") == "LINE" and block.get("Text"):
            lines.append(str(block["Text"]))
    return "\n".join(lines)


def textract_analyze_tables(*, pdf_bytes: bytes) -> dict[str, Any]:
    """
    Analyze tables in a PDF using AWS Textract.
    """

    client = boto3.client("textract", region_name=settings.aws_region)
    response = client.analyze_document(Document={"Bytes": pdf_bytes}, FeatureTypes=["TABLES"])
    return response

