import cv2
import gc
import pytesseract
from collections import defaultdict

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
cv2.setNumThreads(1)

MAX_IMAGE_SIDE = 1080


def shrink_for_ocr(img):
    h, w = img.shape[:2]
    longest = max(h, w)

    if longest <= MAX_IMAGE_SIDE:
        return img

    scale = MAX_IMAGE_SIDE / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)


def build_ocr_gray(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (3, 3), 0)

def process_images_weekly(image_paths):

    brands = defaultdict(int)

    for path in image_paths:

        img = cv2.imread(path)
        if img is None:
            continue

        img = shrink_for_ocr(img)
        gray = build_ocr_gray(img)
        text = pytesseract.image_to_string(gray)

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

        del img
        del gray
        del text
        gc.collect()

    return brands
