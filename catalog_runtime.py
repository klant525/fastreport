import copy
import json
import os
from datetime import datetime

from config_map import BASE_CONFIG_MAP
from model_db import BASE_MODEL_DB

CACHE_PATH = os.path.join(os.path.dirname(__file__), "tgdd_catalog_cache.json")

_RUNTIME_CONFIG_MAP = None
_RUNTIME_MODEL_DB = None
_RUNTIME_META = {}


def _dedupe(items):
    seen = set()
    result = []

    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)

    return result


def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _build_runtime_catalog():
    cache = _load_cache()
    runtime_model_db = copy.deepcopy(BASE_MODEL_DB)
    runtime_config_map = {}

    cache_model_db = cache.get("model_db", {})
    cache_config_map = cache.get("config_map", {})

    for brand, base_models in BASE_MODEL_DB.items():
        models = list(base_models)
        models.extend(cache_model_db.get(brand, []))
        runtime_model_db[brand] = _dedupe(models)

    for brand_models in runtime_model_db.values():
        for model in brand_models:
            configs = list(BASE_CONFIG_MAP.get(model, []))
            configs.extend(cache_config_map.get(model, []))
            if configs:
                runtime_config_map[model] = _dedupe(configs)

    meta = {
        "source": cache.get("source", "base"),
        "updated_at": cache.get("updated_at", ""),
    }

    return runtime_model_db, runtime_config_map, meta


def reload_runtime_catalog():
    global _RUNTIME_CONFIG_MAP, _RUNTIME_MODEL_DB, _RUNTIME_META
    _RUNTIME_MODEL_DB, _RUNTIME_CONFIG_MAP, _RUNTIME_META = _build_runtime_catalog()


def ensure_runtime_catalog():
    global _RUNTIME_CONFIG_MAP, _RUNTIME_MODEL_DB

    if _RUNTIME_CONFIG_MAP is None or _RUNTIME_MODEL_DB is None:
        reload_runtime_catalog()


def get_model_db():
    ensure_runtime_catalog()
    return _RUNTIME_MODEL_DB


def get_config_map():
    ensure_runtime_catalog()
    return _RUNTIME_CONFIG_MAP


def get_catalog_meta():
    ensure_runtime_catalog()
    return _RUNTIME_META
