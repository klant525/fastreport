import cv2
import pytesseract
import re
from collections import defaultdict

# 👉 chỉnh lại nếu path khác
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# =========================
# 🔹 CLEAN TEXT
# =========================
def clean_line(text):
    text = text.lower()

    # bỏ số dài (imei, mã sản phẩm)
    text = re.sub(r'\b\d{6,}\b', '', text)

    # chuẩn hóa dấu +
    text = text.replace("g+", "+").replace("+g", "+")

    # bỏ ký tự rác
    text = re.sub(r'[^a-z0-9\s\+\(\)]', '', text)

    return text.strip()

def normalize_model(text):

    # fix iphone
    text = text.replace("mex", "max")
    text = text.replace("pro mex", "pro max")

    # fix rom
    text = text.replace("266", "256")

    # fix oppo
    text = text.replace("reno155g", "reno 15")
    text = text.replace("reno1s", "reno 15")

    # fix xiaomi
    text = text.replace("1st pro", "11t pro")

    # fix spacing
    text = re.sub(r'\s+', ' ', text)

    return text.strip()

# =========================
# 🔹 EXTRACT CONFIG
# =========================
def extract_config(line):
    match = re.search(r'(\d+)\s*\+\s*(\d+)', line)
    if match:
        ram = match.group(1)
        rom = match.group(2)

        # fix lỗi OCR rom
        if rom == "266":
            rom = "256"

        return f"{ram}/{rom}"
    return ""


# =========================
# 🔹 PROCESS MAIN
# =========================
def process_images(image_paths):

    data = defaultdict(list)

    for path in image_paths:

        img = cv2.imread(path)

        # 👉 cải thiện OCR
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        text = pytesseract.image_to_string(thresh)

        lines = text.split("\n")

        for line in lines:

            l = clean_line(line)
            l = normalize_model(l)

            if len(l) < 5:
                continue

            # =====================
            # 🔹 APPLE
            # =====================
            if "iphone" in l:

                brand = "apple"

                model_match = re.search(r'iphone\s+([\w\s]+?)\s+\d+', l)
                rom_match = re.search(r'(\d+)\s*gb', l)

                model = model_match.group(1).strip() if model_match else ""
                rom = rom_match.group(1) if rom_match else ""

                if not model:
                    continue

                item = f"iPhone {model.title()} ({rom})"

            # =====================
            # 🔹 SAMSUNG
            # =====================
            elif "samsung" in l or "galaxy" in l:

                brand = "samsung"

                model_match = re.search(r'a\s?\d{2,3}', l)
                model = model_match.group(0).replace(" ", "").upper() if model_match else ""

                config = extract_config(l)

                if not model:
                    continue

                item = f"{model} ({config})"

            # =====================
            # 🔹 OPPO
            # =====================
            elif "oppo" in l:

                brand = "oppo"

                config = extract_config(l)

                if "reno" in l:
                    model_match = re.search(r'reno\s?\d+\s?\w*', l)
                    model = model_match.group(0).replace(" ", "").upper() if model_match else ""

                elif "find" in l:
                    model_match = re.search(r'find\s?x\d+', l)
                    model = model_match.group(0).title() if model_match else ""

                elif re.search(r'a\d+', l):
                    model = re.search(r'a\d+', l).group(0).upper()

                else:
                    continue  # bỏ dòng lỗi

                if not model:
                    continue

                item = f"{model} ({config})"

            # =====================
            # 🔹 REALME
            # =====================
            elif "realme" in l:

                brand = "realme"

                model_match = re.search(r'c\d+', l)
                config = extract_config(l)

                model = model_match.group(0).upper() if model_match else ""

                if not model:
                    continue

                item = f"{model} ({config})"

            # =====================
            # 🔹 XIAOMI
            # =====================
            elif "xiaomi" in l:

                brand = "xiaomi"

                model_match = re.search(r'xiaomi\s+([\w\s]+?)\s+\(', l)
                config = extract_config(l)

                model = model_match.group(1).strip() if model_match else ""

                if not model:
                    continue

                item = f"{model.title()} ({config})"

            else:
                continue

            # 👉 add từng máy (KHÔNG gộp)
            data[brand].append(item)

    return data


# =========================
# 🔹 FORMAT REPORT
# =========================
def format_report(data):

    def build(name, flag, label=None):
        items = data.get(name, [])

        # 👉 đếm theo model
        count = {}
        for i in items:
            key = i.lower()
            count[key] = count.get(key, 0) + 1
        total = sum(count.values())

        title = label if label else name.capitalize()

        text = f"{flag} {title}:\n"

        for model, qty in count.items():
            text += f"{qty} {model}\n"

        text += f"\nTotal: {total}\n\n"
        return text

    result = ""

    result += build("samsung", "🇰🇷", "Samsung")
    result += build("apple", "🇺🇸", "Co.A")
    result += build("oppo", "🇨🇳", "Oppo")
    result += build("xiaomi", "🇨🇳", "Xiaomi")
    result += build("vivo", "🇨🇳", "Vivo")
    result += build("realme", "🇨🇳", "Realme")
    result += build("motorola", "🇨🇳", "Motorola")
    result += build("other", "🏴", "Other")

    return result
