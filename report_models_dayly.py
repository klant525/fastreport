import cv2
import easyocr
import re
from collections import defaultdict
from model_db import MODEL_DB

reader = easyocr.Reader(['en'], gpu=False)


# =========================
# CONFIG CHUẨN THEO MODEL
# =========================
MODEL_CONFIG = {
    "iphone": ["64", "128", "256", "512", "1tb"],
    "samsung": ["4/64", "4/128", "6/128", "8/128", "8/256", "12/256"],
    "oppo": ["6/128", "8/128", "8/256", "12/256", "12/512"],
    "realme": ["4/64", "4/128", "6/128", "8/128", "8/256"],
    "xiaomi": ["4/64", "6/128", "8/128", "8/256", "12/256"],
    "motorola": ["4/128", "6/128", "8/128", "8/256"]
}


# =========================
# NORMALIZE
# =========================
def normalize(text):
    text = text.lower()

    text = text.replace("iph0ne", "iphone")
    text = text.replace("ipone", "iphone")

    text = text.replace("mex", "max")
    text = text.replace("pr0", "pro")
    text = text.replace("prs", "pro")

    text = text.replace("12b", "128")
    text = text.replace("1 28", "128")
    text = text.replace("2 56", "256")
    text = text.replace("25 6", "256")
    text = text.replace("26", "256")
    text = text.replace("12g8", "128")

    text = text.replace("g+", "+").replace("+g", "+")

    text = text.replace("renol", "reno")
    text = text.replace("reno1", "reno 1")

    text = re.sub(r'[^a-z0-9\s\+]', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


# =========================
# EXTRACT CONFIG
# =========================
def extract_config(text):

    m = re.search(r'(\d{1,2})\s*\+\s*(\d{2,3})', text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"

    m = re.search(r'(64|128|256|512)\s*gb', text)
    if m:
        return m.group(1)

    if "128" in text:
        return "128"
    if "256" in text:
        return "256"

    return ""


# =========================
# MATCH MODEL
# =========================
def match_model(text, brand):
    for m in MODEL_DB.get(brand, []):
        if m in text:
            return m

    for m in MODEL_DB.get(brand, []):
        words = m.split()
        if len(words) >= 2 and all(w in text for w in words[:2]):
            return m

    return ""


# =========================
# 🔥 LOCK CONFIG
# =========================
def lock_config(model, config, brand):

    if not config:
        return ""

    allowed = MODEL_CONFIG.get(brand, [])

    # iphone chỉ có ROM
    if brand == "apple":
        if config in allowed:
            return config

        # fallback gần đúng
        for a in allowed:
            if config in a:
                return a

        return ""

    # android: ram/rom
    if "/" in config:
        if config in allowed:
            return config

        # fallback gần đúng
        for a in allowed:
            if config.split("/")[1] in a:
                return a

    return ""


# =========================
# OCR 1 ẢNH
# =========================
def process_single_image(path):

    data = defaultdict(list)

    img = cv2.imread(path)
    if img is None:
        return data

    h, w = img.shape[:2]

    # crop bảng
    img = img[int(h*0.25):int(h*0.8), int(w*0.1):int(w*0.95)]

    img = cv2.resize(img, None, fx=1.5, fy=1.5)

    results = reader.readtext(img)

    lines = [r[1] for r in results]

    print("OCR:", lines)

    for line in lines:

        l = normalize(line)

        if len(l) < 6:
            continue

        brand = None

        if "iphone" in l:
            brand = "apple"
        elif "samsung" in l or "galaxy" in l:
            brand = "samsung"
        elif "oppo" in l:
            brand = "oppo"
        elif "realme" in l:
            brand = "realme"
        elif "xiaomi" in l or "redmi" in l or "poco" in l:
            brand = "xiaomi"
        elif "moto" in l:
            brand = "motorola"

        if not brand:
            continue

        model = match_model(l, brand)
        if not model:
            continue

        config = extract_config(l)
        config = lock_config(model, config, brand)

        if config:
            data[brand].append(f"{model} ({config})")
        else:
            data[brand].append(model)

    return data


# =========================
# MULTI IMAGE
# =========================
def process_images(image_paths):

    final = defaultdict(list)

    for path in image_paths:
        single = process_single_image(path)

        for k, v in single.items():
            final[k].extend(v)

    return final


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