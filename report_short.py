import gc
from collections import defaultdict

import cv2

from ocr_backend import build_ocr_variants, cleanup_ocr_resources, extract_text_boxes, merge_boxes_to_lines, normalize_text, shrink_for_ocr
from short_catalog_runtime import get_short_catalog

MAX_IMAGE_SIDE = 1080


def build_catalog(category):
    names = list(get_short_catalog(category))
    catalog = []
    for name in names:
        normalized = normalize_text(name)
        if len(normalized) < 4:
            continue
        catalog.append((name, normalized))
    return sorted(catalog, key=lambda item: -len(item[1]))


def process_short_images(image_paths, categories):
    final = defaultdict(int)
    details = []
    catalog = []

    for category in categories:
        catalog.extend(build_catalog(category))

    try:
        for path in image_paths:
            img = cv2.imread(path)
            image_items = defaultdict(int)

            if img is None:
                details.append({"filename": path, "items": []})
                continue

            gray = None
            binary = None
            lines = []

            try:
                img = shrink_for_ocr(img, MAX_IMAGE_SIDE)
                gray, binary = build_ocr_variants(img)
                seen = set()

                for variant in (gray, binary):
                    for _, line in merge_boxes_to_lines(extract_text_boxes(variant, psm=6)):
                        normalized_line = normalize_text(line)
                        if not normalized_line or normalized_line in seen:
                            continue
                        seen.add(normalized_line)
                        lines.append(normalized_line)

                for line in lines:
                    for raw_name, normalized_name in catalog:
                        if normalized_name in line:
                            image_items[raw_name] += 1

                for name, qty in image_items.items():
                    final[name] += qty

                details.append(
                    {
                        "filename": path,
                        "items": [{"label": name, "qty": qty} for name, qty in sorted(image_items.items())],
                    }
                )
            finally:
                del img
                if gray is not None:
                    del gray
                if binary is not None:
                    del binary
                del lines
                gc.collect()
    finally:
        cleanup_ocr_resources()

    return dict(sorted(final.items())), details


def format_short_report(title, counts):
    total = sum(counts.values())
    text = f"{title}:\n"

    for name, qty in counts.items():
        text += f"{qty} {name.lower()}\n"

    text += f"\nTotal: {total}\n"
    return text
