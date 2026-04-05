from flask import Flask, render_template, request
import os
import uuid

from tgdd_sync import ensure_tgdd_catalog
from catalog_runtime import get_catalog_meta, reload_runtime_catalog
from report_models_dayly import format_report, process_images
from report_models_weekly import process_images_weekly

ensure_tgdd_catalog(max_age_hours=12)
reload_runtime_catalog()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

UPLOAD_FOLDER = "uploads"
MAX_FILES_PER_REQUEST = 12

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def save_uploaded_files(files):
    paths = []

    for file in files[:MAX_FILES_PER_REQUEST]:
        if not file or not file.filename:
            continue

        ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
        path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}{ext}")
        file.save(path)
        paths.append(path)

    return paths


def cleanup_files(paths):
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


@app.after_request
def disable_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.before_request
def sync_catalog_if_needed():
    if ensure_tgdd_catalog(max_age_hours=12):
        reload_runtime_catalog()


@app.route("/", methods=["GET", "POST"])
def index():
    catalog_meta = get_catalog_meta()

    if request.method == "POST":
        files = request.files.getlist("images")
        paths = save_uploaded_files(files)

        if not paths:
            return render_template("uploads.HTML", report="", error="Chua co anh hop le de xu ly.", file_count=0, catalog_meta=catalog_meta, details=[])

        try:
            result, details = process_images(paths)
            report = format_report(result)
            return render_template("uploads.HTML", report=report, error="", file_count=len(paths), catalog_meta=catalog_meta, details=details)
        finally:
            cleanup_files(paths)

    return render_template("uploads.HTML", report="", error="", file_count=0, catalog_meta=catalog_meta, details=[])


@app.route("/weekly", methods=["GET", "POST"])
def weekly():
    catalog_meta = get_catalog_meta()

    if request.method == "POST":
        files = request.files.getlist("images")
        paths = save_uploaded_files(files)

        if not paths:
            return render_template("weekly.html", result=None, error="Chua co anh hop le de xu ly.", file_count=0, catalog_meta=catalog_meta)

        try:
            result = process_images_weekly(paths)
            return render_template("weekly.html", result=result, error="", file_count=len(paths), catalog_meta=catalog_meta)
        finally:
            cleanup_files(paths)

    return render_template("weekly.html", result=None, error="", file_count=0, catalog_meta=catalog_meta)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
