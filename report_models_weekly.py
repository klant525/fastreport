import gc
from collections import defaultdict

import cv2

from ocr_backend import build_ocr_variants, cleanup_ocr_resources, extract_text_boxes, merge_boxes_to_lines, shrink_for_ocr

MAX_IMAGE_SIDE = 960


def process_images_weekly(image_paths):
    brands = defaultdict(int)

    try:
        for path in image_paths:
            img = cv2.imread(path)
            if img is None:
                continue

            gray = None
            binary = None

            try:
                img = shrink_for_ocr(img, MAX_IMAGE_SIDE)
                h, w = img.shape[:2]
                img = img[int(h * 0.22):int(h * 0.82), int(w * 0.05):int(w * 0.98)]
                gray, binary = build_ocr_variants(img)

                found = set()
                seen_lines = set()

                for variant in (gray, binary):
                    for _, line in merge_boxes_to_lines(extract_text_boxes(variant, psm=6)):
                        lowered = line.lower().strip()
                        if not lowered or lowered in seen_lines:
                            continue
                        seen_lines.add(lowered)

                        if "iphone" in lowered:
                            found.add("apple")
                        elif "samsung" in lowered or "galaxy" in lowered:
                            found.add("samsung")
                        elif "oppo" in lowered:
                            found.add("oppo")
                        elif "xiaomi" in lowered or "redmi" in lowered or "poco" in lowered:
                            found.add("xiaomi")
                        elif "vivo" in lowered:
                            found.add("vivo")
                        elif "realme" in lowered:
                            found.add("realme")
                        elif "motorola" in lowered or "moto" in lowered:
                            found.add("motorola")

                for brand in found:
                    brands[brand] += 1
            finally:
                del img
                if gray is not None:
                    del gray
                if binary is not None:
                    del binary
                gc.collect()
    finally:
        cleanup_ocr_resources()

    return brands
