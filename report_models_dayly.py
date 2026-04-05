import cv2
import easyocr
import gc
import re
from collections import defaultdict
from catalog_runtime import get_config_map, get_model_db

cv2.setNumThreads(1)

MAX_IMAGE_SIDE = 1080

reader = None


def get_reader():
    global reader
    if reader is None:
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return reader


def clear_ocr_resources():
    global reader
    reader = None
    gc.collect()


def shrink_for_ocr(img):
    h, w = img.shape[:2]
    longest = max(h, w)

    if longest <= MAX_IMAGE_SIDE:
        return img

    scale = MAX_IMAGE_SIDE / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)


def build_ocr_variants(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(gray)
    binary = cv2.adaptiveThreshold(
        contrast,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    return gray, binary


def read_text_lines(img_variant):
    lines = get_reader().readtext(
        img_variant,
        detail=0,
        paragraph=False,
        decoder="greedy",
        batch_size=1,
        mag_ratio=1.0,
        text_threshold=0.45,
        low_text=0.25,
        link_threshold=0.2,
        width_ths=0.7,
        height_ths=0.7,
    )
    return [line for line in lines if line and line.strip()]


# =========================
# CONFIG CHUẨN
# =========================


# =========================
# NORMALIZE (FIX BUG A26 -> A25)
# =========================
def normalize(text):
    text = text.lower()

    text = text.replace("iph0ne", "iphone")
    text = text.replace("ipone", "iphone")

    text = text.replace("mex", "max")
    text = text.replace("pr0", "pro")
    text = text.replace("prs", "pro")

    # 🔥 FIX: không replace "26" nữa (gây sai model)
    text = text.replace("12b", "128")
    text = text.replace("1 28", "128")
    text = text.replace("2 56", "256")
    text = text.replace("25 6", "256")
    text = text.replace("12g8", "128")

    text = text.replace("g+", "+").replace("+g", "+")

    text = text.replace("renol", "reno")
    text = text.replace("note5g", "note 5g")

    text = re.sub(r'(reno)\s*(\d{2})', r'\1 \2', text)
    text = re.sub(r'(note)\s*(\d{2})', r'\1 \2', text)
    text = re.sub(r'(c)\s*(\d{2})', r'\1\2', text)
    text = re.sub(r'(\d)\s*(gb|tb)\b', r'\1\2', text)

    text = re.sub(r'[^a-z0-9\s\+]', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


# =========================
# EXTRACT CONFIG (FIX MẠNH)
# =========================
def extract_config(text):

    # RAM/ROM
    m = re.search(r'(\d{1,2})\s*[/+]\s*(\d{2,4})', text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"

    # chỉ ROM
    m = re.search(r'(64|128|256|512|1024)\s*(gb|tb)', text)
    if m:
        value = m.group(1)
        unit = m.group(2)
        return "1tb" if value == "1024" or unit == "tb" else value

    # fallback thông minh
    if "128" in text:
        return "128"
    if "256" in text:
        return "256"
    if "512" in text:
        return "512"

    return ""


# =========================
# MATCH MODEL (FIX CHÍNH XÁC HƠN)
# =========================
def match_model(text, brand):
    candidates = get_model_db().get(brand, [])
    compact_text = text.replace(" ", "")

    # 🔥 sort theo độ dài giảm dần (quan trọng)
    candidates = sorted(candidates, key=lambda x: -len(x))

    # match chính xác trước
    for m in candidates:
        if m in text or m.replace(" ", "") in compact_text:
            return m

    # fallback OCR sai nhẹ
    for m in candidates:
        words = m.split()
        if len(words) >= 2 and all(w in text for w in words):
            return m

    return ""


def detect_brand_and_model(text):
    model_db = get_model_db()
    brand_hints = [
        ("apple", ("iphone",)),
        ("samsung", ("samsung", "galaxy")),
        ("oppo", ("oppo", "reno")),
        ("realme", ("realme",)),
        ("xiaomi", ("xiaomi", "redmi", "poco")),
        ("motorola", ("motorola", "moto")),
    ]

    for brand, hints in brand_hints:
        if any(hint in text for hint in hints):
            model = match_model(text, brand)
            if model:
                return brand, model

    for brand in model_db:
        model = match_model(text, brand)
        if model:
            return brand, model

    return None, ""


def make_label(model, config):
    return f"{model} ({config})" if config else model


# =========================
# LOCK CONFIG
# =========================
def lock_config(model, config, brand):

    if not config:
        return ""

    allowed = [item.lower() for item in get_config_map().get(model, [])]
    config = config.lower()

    if not allowed:
        return config

    # iphone
    if brand == "apple":
        if config in allowed:
            return config

        # fallback gần nhất
        for a in allowed:
            if config in a:
                return a

        return allowed[0]

    # android
    if "/" in config:
        if config in allowed:
            return config

        for a in allowed:
            if config.split("/")[1] == a.split("/")[-1]:
                return a

    for a in allowed:
        if a.split("/")[-1] == config:
            return a

    return config


# =========================
# OCR 1 ẢNH (TỐI ƯU RAM)
# =========================
def process_single_image(path):

    data = defaultdict(list)

    img = cv2.imread(path)
    if img is None:
        return data, {"filename": path, "items": []}

    img = shrink_for_ocr(img)

    h, w = img.shape[:2]

    gray = None
    binary = None
    results = None
    image_counts = defaultdict(int)
    detail_items = []

    try:
        # 🔥 crop nhỏ hơn để giảm noise + RAM
        img = img[int(h * 0.3):int(h * 0.75), int(w * 0.1):int(w * 0.95)]

        gray, binary = build_ocr_variants(img)
        results = []
        seen_lines = set()

        for variant in (gray, binary):
            for line in read_text_lines(variant):
                normalized_line = normalize(line)
                if normalized_line in seen_lines:
                    continue
                seen_lines.add(normalized_line)
                results.append(normalized_line)

        for line in results:
            if len(line) < 6:
                continue

            brand, model = detect_brand_and_model(line)
            if not model:
                continue

            config = extract_config(line)
            config = lock_config(model, config, brand)
            label = make_label(model, config)
            image_counts[(brand, label)] += 1

        detail_items = []
        for (brand, label), qty in sorted(image_counts.items(), key=lambda item: (item[0][0], item[0][1])):
            data[brand].extend([label] * qty)
            detail_items.append(
                {
                    "brand": brand,
                    "label": label,
                    "qty": qty,
                }
            )
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

    return data, {"filename": path, "items": detail_items}


# =========================
# MULTI IMAGE (STREAM)
# =========================
def process_images(image_paths):

    final = defaultdict(list)
    details = []

    try:
        for path in image_paths:
            single, detail = process_single_image(path)
            details.append(detail)

            for k, v in single.items():
                final[k].extend(v)
    finally:
        clear_ocr_resources()

    return final, details


# =========================
# FORMAT
# =========================
def format_report(data):

    def build(name, flag):
        items = data.get(name, [])

        count = {}
        for i in items:
            key = i.lower()
            count[key] = count.get(key, 0) + 1

        total = sum(count.values())

        text = f"{flag} {name.upper()}:\n"

        for model, qty in sorted(count.items()):
            text += f"{qty} {model}\n"

        text += f"\nTotal: {total}\n\n"
        return text

    result = ""
    result += build("samsung", "🇰🇷")
    result += build("apple", "🇺🇸")
    result += build("oppo", "🇨🇳")
    result += build("xiaomi", "🇨🇳")
    result += build("realme", "🇨🇳")
    result += build("motorola", "🇨🇳")

    return result
