import json
import os
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen

CACHE_PATH = os.path.join(os.path.dirname(__file__), "tgdd_catalog_cache.json")
CACHE_VERSION = 2
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
BRAND_URLS = {
    "apple": "https://www.thegioididong.com/dtdd-apple-iphone",
    "samsung": "https://www.thegioididong.com/dtdd-samsung",
    "oppo": "https://www.thegioididong.com/dtdd-oppo",
    "realme": "https://www.thegioididong.com/dtdd-realme",
    "xiaomi": "https://www.thegioididong.com/dtdd-xiaomi",
    "motorola": "https://www.thegioididong.com/dtdd-motorola",
}


class AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or self._href is None:
            return

        text = " ".join(part.strip() for part in self._text if part.strip())
        self.links.append((self._href, re.sub(r"\s+", " ", text).strip()))
        self._href = None
        self._text = []


def _read_url(url):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=8) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _normalize_text(text):
    text = text.lower()
    text = text.replace("reno14", "reno 14")
    text = text.replace("reno15", "reno 15")
    text = text.replace("note14", "note 14")
    text = text.replace("note15", "note 15")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _canonical_model(text, brand):
    text = _normalize_text(text)

    if brand == "apple":
        m = re.search(r"iphone\s+\d+(?:e|air)?(?:\s+plus|\s+pro(?:\s+max)?)?", text)
        return m.group(0).strip() if m else ""

    if brand == "samsung":
        m = re.search(r"z\s*(flip|fold)\s*(\d+)(?:\s*(fe))?", text)
        if m:
            suffix = f" {m.group(3)}" if m.group(3) else ""
            return f"z {m.group(1)}{m.group(2)}{suffix}".strip()

        m = re.search(r"(?:samsung\s+galaxy\s+)?([as])\s*(\d{2})(?:\s*(plus|ultra|fe|edge))?", text)
        if m:
            suffix = f" {m.group(3)}" if m.group(3) else ""
            return f"{m.group(1)}{m.group(2)}{suffix}".strip()
        return ""

    if brand == "oppo":
        m = re.search(r"reno\s*(\d{2})(?:\s*(f|pro))?", text)
        if m:
            suffix = f" {m.group(2)}" if m.group(2) else ""
            return f"reno {m.group(1)}{suffix}".strip()
        return ""

    if brand == "realme":
        m = re.search(r"realme\s+note\s*(\d{2})", text)
        if m:
            return f"realme note {m.group(1)}"

        m = re.search(r"\bc\s*(\d{2})\b", text)
        if m:
            return f"c{m.group(1)}"
        return ""

    if brand == "xiaomi":
        m = re.search(r"redmi\s+note\s*(1[45])(?:\s*(pro))?(?:\s*(5g))?", text)
        if m:
            suffix = f" {m.group(2)}" if m.group(2) else ""
            network = f" {m.group(3)}" if m.group(3) and not m.group(2) else ""
            return f"redmi note {m.group(1)}{suffix}{network}".strip()

        m = re.search(r"poco\s*x\s*(\d)(?:\s*(pro))?", text)
        if m:
            suffix = f" {m.group(2)}" if m.group(2) else ""
            return f"poco x{m.group(1)}{suffix}".strip()
        return ""

    if brand == "motorola":
        m = re.search(r"\bg\s*(\d{2})\b", text)
        if m:
            return f"g{m.group(1)}"

        m = re.search(r"edge\s*(\d{2})", text)
        if m:
            return f"edge {m.group(1)}"
        return ""

    return ""


def _extract_configs(text, brand):
    text = _normalize_text(text)
    configs = set()

    for ram, rom in re.findall(r"(\d{1,2})\s*gb\s*[-/]\s*(\d{2,4})\s*gb", text):
        configs.add(f"{int(ram)}/{int(rom)}")

    if brand == "apple":
        for size, unit in re.findall(r"(128|256|512|1|2)\s*(tb|gb)", text):
            configs.add(f"{size}{unit}".lower())
    else:
        ram_values = sorted({int(value) for value in re.findall(r"(\d{1,2})\s*gb", text) if int(value) <= 24})
        rom_values = sorted({int(value) for value in re.findall(r"(64|128|256|512|1024)\s*gb", text)})

        first = re.search(r"(\d{1,2})\s*gb\s*[/]\s*(\d{2,4})\s*gb", text)
        if first:
            configs.add(f"{int(first.group(1))}/{int(first.group(2))}")

        if len(ram_values) == 1 and len(rom_values) > 1:
            for rom in rom_values:
                configs.add(f"{ram_values[0]}/{rom}")

        if len(rom_values) == 1 and len(ram_values) > 1:
            for ram in ram_values:
                configs.add(f"{ram}/{rom_values[0]}")

    normalized = []
    for config in configs:
        normalized.append(config.replace("tb", "tb"))

    return sorted(set(normalized), key=_config_sort_key)


def _config_sort_key(value):
    if "/" not in value:
        if value.endswith("tb"):
            return (100, int(value[:-2]) * 1024)
        return (0, int(value))

    ram, rom = value.split("/", 1)
    rom_value = 1024 if rom.lower() == "1tb" else int(rom)
    return (int(ram), rom_value)


def _scrape_brand_catalog(brand, url):
    html = _read_url(url)
    parser = AnchorCollector()
    parser.feed(html)

    brand_models = {}

    for href, text in parser.links:
        if "/dtdd/" not in href or not text:
            continue

        model = _canonical_model(text, brand)
        if not model:
            continue

        configs = _extract_configs(text, brand)
        brand_models.setdefault(model, set()).update(configs)

    return {
        "models": sorted(brand_models.keys()),
        "configs": {
            model: sorted(configs, key=_config_sort_key)
            for model, configs in brand_models.items()
        },
    }


def _load_cache_meta():
    if not os.path.exists(CACHE_PATH):
        return {}

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _is_cache_fresh(max_age_hours):
    cache = _load_cache_meta()
    if cache.get("version") != CACHE_VERSION:
        return False

    updated_at = cache.get("updated_at")
    if not updated_at:
        return False

    try:
        dt = datetime.fromisoformat(updated_at)
    except ValueError:
        return False

    return datetime.now(timezone.utc) - dt < timedelta(hours=max_age_hours)


def refresh_tgdd_catalog():
    combined_model_db = {}
    combined_config_map = {}

    for brand, url in BRAND_URLS.items():
        try:
            brand_catalog = _scrape_brand_catalog(brand, url)
        except URLError:
            continue
        except Exception:
            continue

        if brand_catalog["models"]:
            combined_model_db[brand] = brand_catalog["models"]
            combined_config_map.update(brand_catalog["configs"])

    if not combined_model_db:
        return False

    payload = {
        "version": CACHE_VERSION,
        "source": "tgdd",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "model_db": combined_model_db,
        "config_map": combined_config_map,
    }

    with open(CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    return True


def ensure_tgdd_catalog(max_age_hours=12):
    if _is_cache_fresh(max_age_hours):
        return False

    return refresh_tgdd_catalog()
