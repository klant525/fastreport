import base64
import gc
import json
import os
import re
from urllib import error, request

import cv2


DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_TIMEOUT = 18
TRUTHY = {"1", "true", "yes", "on"}


def has_openai_vision():
    return bool(os.getenv("OPENAI_API_KEY"))


def is_openai_vision_default_enabled():
    return os.getenv("OPENAI_VISION_ENABLED", "").strip().lower() in TRUTHY and has_openai_vision()


def get_openai_vision_meta():
    return {
        "available": has_openai_vision(),
        "enabled": is_openai_vision_default_enabled(),
        "model": os.getenv("OPENAI_VISION_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "mode": "fallback",
    }


def _resize_and_encode_image(path, max_side=960, max_bytes=420 * 1024):
    img = cv2.imread(path)
    if img is None:
        return ""

    encoded = None

    try:
        h, w = img.shape[:2]
        longest = max(h, w)

        if longest > max_side:
            scale = max_side / float(longest)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            img = cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)

        for quality in (72, 64, 58, 52):
            ok, buffer = cv2.imencode(
                ".jpg",
                img,
                [int(cv2.IMWRITE_JPEG_QUALITY), quality],
            )
            if not ok:
                continue

            encoded = buffer.tobytes()
            if len(encoded) <= max_bytes:
                break

        if not encoded:
            return ""

        return base64.b64encode(encoded).decode("ascii")
    finally:
        del img
        if encoded is not None:
            del encoded
        gc.collect()


def _extract_output_text(payload):
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)

    return "\n".join(parts).strip()


def _split_product_rows(text):
    raw = (text or "").strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass

    normalized = raw.replace("\r", "\n").replace(";", "\n")
    lines = [line.strip(" -\t") for line in normalized.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines

    expanded = re.sub(
        r"(?i)\s+(?=(dien thoai\s+iphone|iphone|oppo|samsung|xiaomi|redmi|poco|realme|honor|vivo|moto|motorola))",
        "\n",
        raw,
    )
    return [line.strip(" -\t") for line in expanded.splitlines() if line.strip()]


def extract_phone_lines(path, enabled=False):
    if not enabled or not has_openai_vision():
        return []

    image_data = _resize_and_encode_image(path)
    if not image_data:
        return []

    model = os.getenv("OPENAI_VISION_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    prompt = (
        "Read this smartphone price-list image and extract every visible product row from the product-name column. "
        "Keep duplicate rows if the same product appears multiple times. "
        "Keep the phone model words and any RAM/ROM or storage info you can read. "
        "Ignore headers, filters, menu bars, codes, quantities, prices, and non-product UI text. "
        "Return only a JSON array of product-row strings, in reading order, with duplicates preserved. "
        "If a row is blurry, make your best effort to read the phone model and storage from the visible text."
    )
    body = {
        "model": model,
        "max_output_tokens": 900,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_data}",
                        "detail": "high",
                    },
                ],
            }
        ],
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=DEFAULT_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return []

    text = _extract_output_text(payload)
    return _split_product_rows(text)
