from __future__ import annotations

import json
from typing import Any

import boto3

from core.settings import settings


def _invoke_bedrock(*, model_id: str, prompt: str) -> str:
    """
    Invoke Bedrock model and return plain text output.
    """

    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    # Minimal Claude-compatible schema; exact payload may vary by Bedrock provider version.
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 128,
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
    Classify document type using Claude Haiku (Bedrock, ap-south-1).
    """

    prompt = (
        "Classify this document as one of: form16, bank_statement, ais, 26as, capital_gains, unknown. "
        "Reply with ONLY the classification word.\n\n"
        f"{raw_text[:8000]}"
    )
    # Model ID placeholder; configure per your Bedrock account.
    return _invoke_bedrock(model_id="anthropic.claude-3-haiku-20240307-v1:0", prompt=prompt).splitlines()[0].strip()


def sonnet_explain_anomalies(*, findings: list[dict[str, Any]]) -> str:
    """
    Explain mismatches for CA review using Claude Sonnet.

    Never request or suggest numeric calculations.
    """

    prompt = (
        "Explain this mismatch in simple terms a CA can understand. Do not suggest any numbers.\n\n"
        f"{findings}"
    )
    return _invoke_bedrock(model_id="anthropic.claude-3-sonnet-20240229-v1:0", prompt=prompt)

