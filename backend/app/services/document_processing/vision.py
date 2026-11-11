import base64
import http.client
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.document_processing.base import ProcessingError


def vision_enabled() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def describe_image(image_bytes: bytes, mime_type: str) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Describe only meaningful information visible in this "
                            "document visual, such as a chart, diagram, or labeled "
                            "figure. Be concise and do not infer missing data."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ]
    }
    request = Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        ),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        http.client.HTTPException,
        json.JSONDecodeError,
    ) as error:
        raise ProcessingError("Gemini could not describe an embedded visual.") from error

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"].strip() or None
    except (KeyError, IndexError, TypeError) as error:
        raise ProcessingError("Gemini returned an invalid visual description.") from error


def should_describe_image(
    width: int,
    height: int,
    described_count: int,
) -> bool:
    return width * height >= 160_000 and described_count < 10
