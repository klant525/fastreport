import json
import os

from tgdd_sync import SHORT_CACHE_PATH

_RUNTIME_SHORT_CATALOG = None
_RUNTIME_META = {}


def _load_cache():
    if not os.path.exists(SHORT_CACHE_PATH):
        return {}

    try:
        with open(SHORT_CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def reload_short_catalog():
    global _RUNTIME_SHORT_CATALOG, _RUNTIME_META
    cache = _load_cache()
    _RUNTIME_SHORT_CATALOG = cache.get("data", {})
    _RUNTIME_META = {
        "source": cache.get("source", "base"),
        "updated_at": cache.get("updated_at", ""),
    }


def ensure_short_catalog_loaded():
    global _RUNTIME_SHORT_CATALOG
    if _RUNTIME_SHORT_CATALOG is None:
        reload_short_catalog()


def get_short_catalog(category):
    ensure_short_catalog_loaded()
    return _RUNTIME_SHORT_CATALOG.get(category, [])


def get_short_catalog_meta():
    ensure_short_catalog_loaded()
    return _RUNTIME_META
