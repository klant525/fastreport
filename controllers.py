import os
import uuid

from flask import Blueprint, Response, current_app, render_template, request

from catalog_runtime import get_catalog_meta, reload_runtime_catalog
from ocr_backend import is_tesseract_available
from report_models_dayly import format_report, process_images
from report_models_weekly import process_images_weekly
from report_short import format_short_report, process_short_images
from security_utils import is_allowed_upload
from short_catalog_runtime import get_short_catalog_meta, reload_short_catalog
from tgdd_sync import ensure_short_catalog, ensure_tgdd_catalog

main_bp = Blueprint("main", __name__)


def save_uploaded_files(files):
    paths = []
    max_files = current_app.config["MAX_FILES_PER_REQUEST"]
    upload_folder = current_app.config["UPLOAD_FOLDER"]

    for file in files[:max_files]:
        if not file or not file.filename:
            continue
        if not is_allowed_upload(file):
            continue

        ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
        path = os.path.join(upload_folder, f"{uuid.uuid4()}{ext}")
        file.save(path)
        paths.append(path)

    return paths


def cleanup_files(paths):
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def build_seo(page_title, description, path):
    site_name = current_app.config.get("SITE_NAME", "FastReport")
    site_url = current_app.config.get("SITE_URL", "").rstrip("/")
    canonical_url = f"{site_url}{path}" if site_url else path
    return {
        "title": f"{page_title} | {site_name}",
        "description": description,
        "canonical_url": canonical_url,
        "site_name": site_name,
    }


def common_template_context():
    return {
        "vision_meta": current_app.config.get("OPENAI_VISION", {}),
        "ocr_meta": {
            "tesseract_available": is_tesseract_available(),
        },
    }


def _humanize_processing_error(exc):
    message = str(exc).strip()
    if not message:
        return "Co loi xay ra trong luc xu ly anh."
    return message


@main_bp.before_app_request
def sync_catalog_if_needed():
    ensure_tgdd_catalog(max_age_hours=12)
    ensure_short_catalog(max_age_hours=12)
    reload_runtime_catalog()
    reload_short_catalog()


@main_bp.route("/", methods=["GET", "POST"])
def index():
    catalog_meta = get_catalog_meta()
    seo = build_seo(
        "Daily OCR Report",
        "Tao bao cao dien thoai daily tu anh bang gia TGDD bang OCR, toi uu cho deploy VPS nhe RAM.",
        "/",
    )

    if request.method == "POST":
        files = request.files.getlist("images")
        use_gpt = request.form.get("use_gpt") == "1"
        paths = save_uploaded_files(files)

        if not paths:
            return render_template("uploads.HTML", report="", error="Chua co anh hop le de xu ly.", file_count=0, catalog_meta=catalog_meta, details=[], seo=seo, use_gpt=use_gpt, **common_template_context())

        try:
            result, details = process_images(paths, use_gpt=use_gpt)
            report = format_report(result)
            return render_template("uploads.HTML", report=report, error="", file_count=len(paths), catalog_meta=catalog_meta, details=details, seo=seo, use_gpt=use_gpt, **common_template_context())
        except Exception as exc:
            return render_template("uploads.HTML", report="", error=_humanize_processing_error(exc), file_count=len(paths), catalog_meta=catalog_meta, details=[], seo=seo, use_gpt=use_gpt, **common_template_context()), 500
        finally:
            cleanup_files(paths)

    return render_template("uploads.HTML", report="", error="", file_count=0, catalog_meta=catalog_meta, details=[], seo=seo, use_gpt=False, **common_template_context())


@main_bp.route("/weekly", methods=["GET", "POST"])
def weekly():
    catalog_meta = get_catalog_meta()
    seo = build_seo(
        "Weekly Brand Report",
        "Bao cao tong hop theo hang dien thoai tu nhieu anh bang gia, phu hop de thong ke nhanh theo tuan.",
        "/weekly",
    )

    if request.method == "POST":
        files = request.files.getlist("images")
        paths = save_uploaded_files(files)

        if not paths:
            return render_template("weekly.html", result=None, error="Chua co anh hop le de xu ly.", file_count=0, catalog_meta=catalog_meta, seo=seo, **common_template_context())

        try:
            result = process_images_weekly(paths)
            return render_template("weekly.html", result=result, error="", file_count=len(paths), catalog_meta=catalog_meta, seo=seo, **common_template_context())
        except Exception as exc:
            return render_template("weekly.html", result=None, error=_humanize_processing_error(exc), file_count=len(paths), catalog_meta=catalog_meta, seo=seo, **common_template_context()), 500
        finally:
            cleanup_files(paths)

    return render_template("weekly.html", result=None, error="", file_count=0, catalog_meta=catalog_meta, seo=seo, **common_template_context())


@main_bp.route("/accessories", methods=["GET", "POST"])
def accessories():
    catalog_meta = get_short_catalog_meta()
    seo = build_seo(
        "Accessories OCR Report",
        "Bao cao OCR rieng cho tai nghe va smartwatch dang kinh doanh tren TGDD.",
        "/accessories",
    )

    if request.method == "POST":
        files = request.files.getlist("images")
        paths = save_uploaded_files(files)

        if not paths:
            return render_template("short_report.html", report="", details=[], error="Chua co anh hop le de xu ly.", file_count=0, catalog_meta=catalog_meta, page_title="Accessories Report", route_name="accessories", seo=seo, **common_template_context())

        try:
            counts, details = process_short_images(paths, ["audio", "watch"])
            report = format_short_report("ACCESSORIES", counts)
            return render_template("short_report.html", report=report, details=details, error="", file_count=len(paths), catalog_meta=catalog_meta, page_title="Accessories Report", route_name="accessories", seo=seo, **common_template_context())
        except Exception as exc:
            return render_template("short_report.html", report="", details=[], error=_humanize_processing_error(exc), file_count=len(paths), catalog_meta=catalog_meta, page_title="Accessories Report", route_name="accessories", seo=seo, **common_template_context()), 500
        finally:
            cleanup_files(paths)

    return render_template("short_report.html", report="", details=[], error="", file_count=0, catalog_meta=catalog_meta, page_title="Accessories Report", route_name="accessories", seo=seo, **common_template_context())


@main_bp.route("/tablets", methods=["GET", "POST"])
def tablets():
    catalog_meta = get_short_catalog_meta()
    seo = build_seo(
        "Tablet OCR Report",
        "Bao cao OCR rieng cho may tinh bang dang kinh doanh tren TGDD, de doi chieu nhanh tu anh bang gia.",
        "/tablets",
    )

    if request.method == "POST":
        files = request.files.getlist("images")
        paths = save_uploaded_files(files)

        if not paths:
            return render_template("short_report.html", report="", details=[], error="Chua co anh hop le de xu ly.", file_count=0, catalog_meta=catalog_meta, page_title="Tablet Report", route_name="tablets", seo=seo, **common_template_context())

        try:
            counts, details = process_short_images(paths, ["tablet"])
            report = format_short_report("TABLETS", counts)
            return render_template("short_report.html", report=report, details=details, error="", file_count=len(paths), catalog_meta=catalog_meta, page_title="Tablet Report", route_name="tablets", seo=seo, **common_template_context())
        except Exception as exc:
            return render_template("short_report.html", report="", details=[], error=_humanize_processing_error(exc), file_count=len(paths), catalog_meta=catalog_meta, page_title="Tablet Report", route_name="tablets", seo=seo, **common_template_context()), 500
        finally:
            cleanup_files(paths)

    return render_template("short_report.html", report="", details=[], error="", file_count=0, catalog_meta=catalog_meta, page_title="Tablet Report", route_name="tablets", seo=seo, **common_template_context())


@main_bp.route("/robots.txt")
def robots():
    site_url = current_app.config.get("SITE_URL", "").rstrip("/")
    sitemap_url = f"{site_url}/sitemap.xml" if site_url else "/sitemap.xml"
    content = f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n"
    return Response(content, mimetype="text/plain")


@main_bp.route("/sitemap.xml")
def sitemap():
    site_url = current_app.config.get("SITE_URL", "").rstrip("/")
    pages = ["/", "/weekly", "/accessories", "/tablets"]

    xml_items = []
    for path in pages:
        loc = f"{site_url}{path}" if site_url else path
        xml_items.append(f"<url><loc>{loc}</loc></url>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(xml_items)}"
        "</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@main_bp.route("/healthz")
def healthz():
    return {"status": "ok"}
