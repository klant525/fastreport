import cv2
import pytesseract
from collections import defaultdict

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def process_images_weekly(image_paths):

    brands = defaultdict(int)

    for path in image_paths:

        img = cv2.imread(path)
        text = pytesseract.image_to_string(img)

        lines = text.split("\n")

        found = set()  # 👉 tránh đếm trùng trong 1 ảnh

        for line in lines:

            l = line.lower()

            if "iphone" in l:
                found.add("apple")

            elif "samsung" in l or "galaxy" in l:
                found.add("samsung")

            elif "oppo" in l:
                found.add("oppo")

            elif "xiaomi" in l or "redmi" in l:
                found.add("xiaomi")

            elif "vivo" in l:
                found.add("vivo")

            elif "realme" in l:
                found.add("realme")

            elif "motorola" in l or "moto" in l:
                found.add("motorola")

        # 👉 cộng theo ảnh (logic tuần)
        for b in found:
            brands[b] += 1

    return brands