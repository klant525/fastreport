import os
import time
from collections import defaultdict, deque


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_PREFIXES = ("image/",)


def is_allowed_upload(file_storage):
    filename = getattr(file_storage, "filename", "") or ""
    content_type = (getattr(file_storage, "content_type", "") or "").lower()
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False

    return any(content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES)


def cleanup_stale_uploads(upload_folder, max_age_seconds=900):
    if not os.path.isdir(upload_folder):
        return

    now = time.time()
    for entry in os.scandir(upload_folder):
        if not entry.is_file():
            continue

        try:
            if now - entry.stat().st_mtime > max_age_seconds:
                os.remove(entry.path)
        except OSError:
            continue


class SimpleRateLimiter:
    def __init__(self, max_requests=18, window_seconds=300):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)

    def allow(self, key):
        now = time.time()
        bucket = self._hits[key]

        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            return False

        bucket.append(now)
        return True
