import gc
import re
from collections import defaultdict

import cv2

from catalog_runtime import get_config_map, get_model_db
from ocr_backend import build_ocr_variants, cleanup_ocr_resources, extract_text_boxes, merge_boxes_to_lines, shrink_for_ocr
from openai_vision import extract_phone_lines

MAX_IMAGE_SIDE = 960


def normalize(text):
    text = text.lower()

    replacements = {
        "iph0ne": "iphone",
        "ipone": "iphone",
        "mex": "max",
        "pr0": "pro",
        "prs": "pro",
        "12b": "128",
        "1 28": "128",
        "2 56": "256",
        "25 6": "256",
        "12g8": "128",
        "g+": "+",
        "+g": "+",
        "renol": "reno",
        "note5g": "note 5g",
        "5 g": "5g",
        "1tb": "1024gb",
        "l28": "128",
        "z56": "256",
        "s 24": "s24",
        "s 25": "s25",
        "s 26": "s26",
        "a 07": "a07",
        "a 17": "a17",
        "a 26": "a26",
        "a 36": "a36",
        "a 56": "a56",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = re.sub(r"(reno)\s*(\d{2})", r"\1 \2", text)
    text = re.sub(r"(note)\s*(\d{2})", r"\1 \2", text)
    text = re.sub(r"(c)\s*(\d{2})", r"\1\2", text)
    text = re.sub(r"(s)(\d{2})(ultra|plus|fe)\b", r"\1\2 \3", text)
    text = re.sub(r"(a)(0?\d{2})(5g)\b", r"\1\2 \3", text)
    text = re.sub(r"(\d)\s*(gb|tb)\b", r"\1\2", text)
    text = re.sub(r"(\d{1,2})\s*[-/+xх]\s*(\d{2,4})", r"\1/\2", text)
    text = re.sub(r"\b(4|6|8|12)(64|128|256|512)\b", r"\1/\2", text)
    text = re.sub(r"[^a-z0-9\s/+]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_config(text):
    match = re.search(r"(\d{1,2})\s*[-/+]\s*(64|128|256|512|1024)", text)
    if match:
        return f"{match.group(1)}/{match.group(2)}"

    match = re.search(r"\b(4|6|8|12)\s*(64|128|256|512)\b", text)
    if match:
        return f"{match.group(1)}/{match.group(2)}"

    match = re.search(r"(64|128|256|512|1024)\s*(gb|tb)", text)
    if match:
        value = match.group(1)
        unit = match.group(2)
        return "1tb" if value == "1024" or unit == "tb" else value

    for rom in ("512", "256", "128", "64"):
        if rom in text:
            return rom

    return ""


DESCRIPTOR_TOKENS = {"plus", "pro", "max", "ultra", "fe", "air", "mini", "flip", "fold", "5g"}
NON_PRODUCT_HINTS = {
    "trang thai",
    "khu vuc",
    "tat ca",
    "ma san pham",
    "ten san pham",
    "san xuat hang",
    "smartphone",
    "cap nhat",
    "phien ban",
    "kho",
    "moi",
}


def tokenize_model_text(text):
    return [token for token in re.split(r"\s+", text.strip()) if token]


def model_candidate_score(text, model):
    text_tokens = set(tokenize_model_text(text))
    model_tokens = tokenize_model_text(model)
    compact_text = text.replace(" ", "")
    compact_model = model.replace(" ", "")

    model_numbers = set(re.findall(r"\d+", model))
    text_numbers = set(re.findall(r"\d+", text))
    if model_numbers and not model_numbers.issubset(text_numbers):
        return -1

    model_descriptors = {token for token in model_tokens if token in DESCRIPTOR_TOKENS}
    if model_descriptors and not model_descriptors.issubset(text_tokens):
        return -1

    if compact_model in compact_text:
        score = 120 + min(len(compact_model), 24)
        if model_descriptors:
            score += 12
        return score

    hits = sum(1 for token in model_tokens if token in text_tokens)
    if hits != len(model_tokens):
        return -1

    score = 70 + hits * 10 + min(len(compact_model), 20)
    if model_descriptors:
        score += 8
    return score


def is_product_like_line(text):
    if len(text) < 8:
        return False

    lowered = text.lower()
    if any(hint in lowered for hint in NON_PRODUCT_HINTS):
        return False

    if lowered.startswith("013") and "iphone" not in lowered and "samsung" not in lowered and "galaxy" not in lowered:
        return False

    product_tokens = (
        "iphone",
        "galaxy",
        "samsung",
        "oppo",
        "reno",
        "realme",
        "xiaomi",
        "redmi",
        "poco",
        "motorola",
        "moto",
        "dien thoai",
    )
    if any(token in lowered for token in product_tokens):
        return True

    return bool(re.search(r"\b(s\d{2}|a\d{2}|g\d{2}|note\s?\d{2}|c\d{2})\b", lowered))


def match_model(text, brand):
    candidates = get_model_db().get(brand, [])
    best_model = ""
    best_score = 0

    for model in sorted(candidates, key=lambda item: -len(item)):
        if re.search(rf"(?<![a-z0-9]){re.escape(model)}(?![a-z0-9])", text):
            return model

        score = model_candidate_score(text, model)
        if score < 0:
            continue
        if score > best_score:
            best_score = score
            best_model = model

    return best_model if best_score >= 70 else ""


def detect_brand_and_model(text):
    model_db = get_model_db()
    brand_hints = [
        ("apple", ("iphone",)),
        ("samsung", ("samsung", "galaxy", "s24", "s25", "s26", "a07", "a17", "a26", "a36", "a56", "z flip", "z fold")),
        ("oppo", ("oppo", "reno", "find", "a6 pro")),
        ("realme", ("realme", "c61", "c65", "c67", "c71", "c75", "c85")),
        ("xiaomi", ("xiaomi", "redmi", "poco", "note 14", "note 15", "15t")),
        ("motorola", ("motorola", "moto", "g54", "g84")),
    ]

    for brand, hints in brand_hints:
        if any(hint in text for hint in hints):
            model = match_model(text, brand)
            if model:
                return brand, model

    if not re.search(r"(iphone|galaxy|s\d{2}|a\d{2}|reno|note|realme|poco|redmi|moto|motorola|g\d{2}|find|15t|c\d{2})", text):
        return None, ""

    for brand in model_db:
        model = match_model(text, brand)
        if model:
            return brand, model

    return None, ""


def make_label(model, config):
    return f"{model} ({config})" if config else model


def lock_config(model, config, brand):
    if not config:
        return ""

    allowed = [item.lower() for item in get_config_map().get(model, [])]
    config = config.lower()

    if not allowed:
        return config

    if brand == "apple":
        if config in allowed:
            return config
        for allowed_item in allowed:
            if config in allowed_item:
                return allowed_item
        return allowed[0]

    if "/" in config:
        if config in allowed:
            return config

        config_ram, config_rom = config.split("/", 1)
        for allowed_item in allowed:
            allowed_ram, allowed_rom = allowed_item.split("/", 1)
            if config_rom == allowed_rom:
                return allowed_item
            if config_ram == allowed_ram:
                return allowed_item

    for allowed_item in allowed:
        if allowed_item.split("/")[-1] == config:
            return allowed_item

    return config


def collect_matches(lines, image_counts):
    for line in lines:
        if len(line) < 5 or not is_product_like_line(line):
            continue

        brand, model = detect_brand_and_model(line)
        if not model:
            continue

        config = extract_config(line)
        config = lock_config(model, config, brand)
        label = make_label(model, config)
        image_counts[(brand, label)] += 1


def line_fingerprint(text):
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = text.replace("1024gb", "1tb")
    text = text.replace("gb", "")
    text = text.replace("tb", "")
    text = re.sub(r"\([^)]*\)", "", text)
    return text


def row_bucket(y_center, size=14):
    return int(round(float(y_center) / float(size)))


def compress_debug_lines(lines, limit=24):
    cleaned = [line for line in lines if line]
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + [f"... ({len(cleaned) - limit} dong nua)"]


def process_single_image(path, use_gpt=False):
    data = defaultdict(list)

    img = cv2.imread(path)
    if img is None:
        return data, {"filename": path, "items": [], "local_ocr_lines": [], "gpt_lines": [], "used_gpt": False}

    img = shrink_for_ocr(img, MAX_IMAGE_SIDE)
    h, w = img.shape[:2]

    gray = None
    binary = None
    results = None
    image_counts = defaultdict(int)
    detail_items = []
    local_debug_lines = []
    gpt_debug_lines = []
    gpt_match_lines = []
    used_gpt = False

    try:
        img = img[int(h * 0.24):int(h * 0.8), int(w * 0.06):int(w * 0.97)]
        results = []
        seen_line_keys = set()
        gray, binary = build_ocr_variants(img)

        for variant in (gray, binary):
            merged_lines = merge_boxes_to_lines(extract_text_boxes(variant, psm=6))
            for y_center, line in merged_lines:
                normalized_line = normalize(line)
                fingerprint = line_fingerprint(normalized_line)
                line_key = (row_bucket(y_center), fingerprint)
                if not normalized_line or line_key in seen_line_keys:
                    continue
                seen_line_keys.add(line_key)
                results.append(normalized_line)
                local_debug_lines.append(normalized_line)

        if use_gpt:
            gpt_lines = extract_phone_lines(path, enabled=True)
            used_gpt = bool(gpt_lines)
            for line in gpt_lines:
                normalized_line = normalize(line)
                if normalized_line:
                    gpt_match_lines.append(normalized_line)
                    gpt_debug_lines.append(normalized_line)

        source_lines = results
        if use_gpt and gpt_match_lines:
            source_lines = gpt_match_lines

        collect_matches(source_lines, image_counts)

        for (brand, label), qty in sorted(image_counts.items(), key=lambda item: (item[0][0], item[0][1])):
            data[brand].extend([label] * qty)
            detail_items.append({"brand": brand, "label": label, "qty": qty})
    finally:
        del img
        if gray is not None:
            del gray
        if binary is not None:
            del binary
        if results is not None:
            del results
        del image_counts
        gc.collect()

    return data, {
        "filename": path,
        "items": detail_items,
        "local_ocr_lines": compress_debug_lines(local_debug_lines),
        "gpt_lines": compress_debug_lines(gpt_debug_lines),
        "used_gpt": used_gpt,
    }


def process_images(image_paths, use_gpt=False):
    final = defaultdict(list)
    details = []

    try:
        for path in image_paths:
            single, detail = process_single_image(path, use_gpt=use_gpt)
            details.append(detail)

            for brand, items in single.items():
                final[brand].extend(items)
    finally:
        cleanup_ocr_resources()

    return final, details


def format_report(data):
    brand_flags = {
        "samsung": "🇰🇷",
        "apple": "🇺🇸",
        "oppo": "🇨🇳",
        "xiaomi": "🇨🇳",
        "realme": "🇨🇳",
        "motorola": "🇺🇸",
    }

    def build(name, flag):
        items = data.get(name, [])
        count = {}

        for item in items:
            key = item.lower()
            count[key] = count.get(key, 0) + 1

        total = sum(count.values())
        text = f"{flag} {name.upper()}:\n"

        for model, qty in sorted(count.items()):
            text += f"{qty} {model}\n"

        text += f"\nTotal: {total}\n\n"
        return text

    result = ""
    result += build("samsung", brand_flags["samsung"])
    result += build("apple", brand_flags["apple"])
    result += build("oppo", brand_flags["oppo"])
    result += build("xiaomi", brand_flags["xiaomi"])
    result += build("realme", brand_flags["realme"])
    result += build("motorola", brand_flags["motorola"])
    return result
