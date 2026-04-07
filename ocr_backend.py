import gc
import os
import re
import shutil

import cv2
import pytesseract
from pytesseract import TesseractNotFoundError

cv2.setNumThreads(1)

TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
else:
    detected = shutil.which("tesseract")
    if detected:
        pytesseract.pytesseract.tesseract_cmd = detected


def cleanup_ocr_resources():
    gc.collect()


def is_tesseract_available():
    configured = getattr(pytesseract.pytesseract, "tesseract_cmd", "").strip()
    if configured and os.path.exists(configured):
        return True
    return shutil.which("tesseract") is not None


def shrink_for_ocr(img, max_image_side):
    h, w = img.shape[:2]
    longest = max(h, w)

    if longest <= max_image_side:
        return img

    scale = max_image_side / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)


def build_ocr_variants(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(gray)
    sharpened = cv2.addWeighted(
        contrast,
        1.35,
        cv2.GaussianBlur(contrast, (0, 0), 2.2),
        -0.35,
        0,
    )
    binary = cv2.adaptiveThreshold(
        sharpened,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    return gray, binary


def extract_text_boxes(img_variant, psm=6):
    try:
        data = pytesseract.image_to_data(
            img_variant,
            output_type=pytesseract.Output.DICT,
            config=f"--oem 3 --psm {psm}",
        )
    except TesseractNotFoundError as exc:
        raise RuntimeError(
            "Khong tim thay OCR engine 'tesseract'. Tren Linux/VPS hay cai goi tesseract-ocr. "
            "Neu dang test local, can cai Tesseract va them vao PATH hoac set TESSERACT_CMD."
        ) from exc

    boxes = []
    count = len(data.get("text", []))
    for index in range(count):
        text = (data["text"][index] or "").strip()
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1.0

        if not text or confidence < 20:
            continue

        left = int(data["left"][index])
        top = int(data["top"][index])
        height = int(data["height"][index])
        y_center = top + (height / 2.0)
        boxes.append((y_center, left, text))

    return boxes


def merge_boxes_to_lines(boxes, y_tolerance=18):
    lines = []

    for y_center, x_left, text in sorted(boxes, key=lambda item: (item[0], item[1])):
        placed = False
        for line in lines:
            if abs(line["y"] - y_center) <= y_tolerance:
                line["parts"].append((x_left, text))
                line["y"] = (line["y"] + y_center) / 2.0
                placed = True
                break

        if not placed:
            lines.append({"y": y_center, "parts": [(x_left, text)]})

    merged = []
    for line in lines:
        ordered = [part for _, part in sorted(line["parts"], key=lambda item: item[0])]
        merged.append((line["y"], " ".join(ordered)))
    return merged


def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s/+]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
