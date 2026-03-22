from __future__ import annotations

import json
import logging
from typing import Any

import boto3

from core.settings import settings

logger = logging.getLogger("smartitr")

# ---------------------------------------------------------------------------
# Bedrock model IDs — ap-south-1 in-region ONLY (never global cross-region)
# ---------------------------------------------------------------------------
# These are the canonical in-region inference profile IDs for ap-south-1.
# Do NOT use the bare anthropic.* model IDs — those default to cross-region
# routing which violates the DPDP Act / data residency requirement.
import os
HAIKU_MODEL_ID = os.getenv("BEDROCK_HAIKU_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
SONNET_MODEL_ID = os.getenv("BEDROCK_SONNET_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")


def _invoke_bedrock(*, model_id: str, prompt: str, max_tokens: int = 2048) -> str:
    """
    Invoke a Bedrock model (ap-south-1 in-region) and return plain text output.

    max_tokens defaults to 2048 — enough for a full multi-field extraction JSON.
    For classification (single-word reply) callers can pass max_tokens=32.
    """
    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = client.invoke_model(modelId=model_id, body=json.dumps(body).encode("utf-8"))
    raw = response.get("body")
    try:
        data = json.loads(raw.read().decode("utf-8")) if raw else {}
        text = data.get("content", [{}])[0].get("text", "") if "content" in data else ""
    except Exception:
        text = ""
    return text.strip()


def haiku_classify_document(*, raw_text: str) -> str:
    """
    Classify document type using Claude Haiku (Bedrock, ap-south-1 in-region).
    Reply is a single word — max_tokens=32 is sufficient and minimises cost.
    """
    prompt = (
        "Classify this document as one of: form16, bank_statement, ais, 26as, capital_gains, unknown. "
        "Reply with ONLY that single classification word, nothing else.\n\n"
        f"{raw_text[:2000]}"
    )
    result = _invoke_bedrock(model_id=HAIKU_MODEL_ID, prompt=prompt, max_tokens=32)
    # Defensive: take first token only, lowercase
    first_word = result.splitlines()[0].strip().lower()
    valid = {"form16", "bank_statement", "ais", "26as", "capital_gains", "unknown"}
    return first_word if first_word in valid else "unknown"


def sonnet_explain_anomalies(*, findings: list[dict[str, Any]]) -> str:
    """
    Explain mismatches for CA review using Claude Sonnet (ap-south-1 in-region).

    STRICT CONTRACT:
    - Write plain-English explanation aimed at a Chartered Accountant.
    - NEVER suggest a number, a filing position, or a tax calculation.
    - NEVER say "you should" — only describe what was observed.
    """
    prompt = (
        "You are an assistant to a Chartered Accountant reviewing tax documents. "
        "Explain the following data mismatches in clear, plain English. "
        "Do NOT suggest any numbers, corrections, or what the CA should do — only describe the discrepancy.\n\n"
        f"Mismatches found:\n{json.dumps(findings, indent=2)}"
    )
    return _invoke_bedrock(model_id=SONNET_MODEL_ID, prompt=prompt, max_tokens=512)

