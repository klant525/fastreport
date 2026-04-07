import os

from flask import Flask, abort, request

from catalog_runtime import reload_runtime_catalog
from controllers import main_bp
from env_loader import load_local_env
from openai_vision import get_openai_vision_meta
from security_utils import SimpleRateLimiter, cleanup_stale_uploads
from short_catalog_runtime import reload_short_catalog
from tgdd_sync import ensure_short_catalog, ensure_tgdd_catalog

upload_rate_limiter = SimpleRateLimiter(max_requests=12, window_seconds=300)


def create_app():
    load_local_env()
    ensure_tgdd_catalog(max_age_hours=12)
    ensure_short_catalog(max_age_hours=12)
    reload_runtime_catalog()
    reload_short_catalog()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
    app.config["MAX_FILES_PER_REQUEST"] = 12
    app.config["UPLOAD_TTL_SECONDS"] = 900
    app.config["SITE_NAME"] = "FastReport"
    app.config["SITE_URL"] = os.getenv("SITE_URL", "").rstrip("/")
    app.config["OPENAI_VISION"] = get_openai_vision_meta()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "0") == "1"

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    cleanup_stale_uploads(app.config["UPLOAD_FOLDER"], app.config["UPLOAD_TTL_SECONDS"])

    @app.before_request
    def guard_requests():
        cleanup_stale_uploads(app.config["UPLOAD_FOLDER"], app.config["UPLOAD_TTL_SECONDS"])

        if request.method != "POST":
            return None

        if request.endpoint in {"main.index", "main.weekly", "main.accessories", "main.tablets"}:
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            if not upload_rate_limiter.allow(client_ip):
                abort(429)

        return None

    @app.after_request
    def disable_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; "
            "font-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        if response.mimetype == "text/html":
            response.headers["Clear-Site-Data"] = '"cache", "storage"'
        return response

    @app.errorhandler(429)
    def too_many_requests(_error):
        return (
            "Too many upload requests. Please wait a few minutes and try again.",
            429,
            {"Retry-After": "300"},
        )

    app.register_blueprint(main_bp)
    return app


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0")
