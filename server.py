import os
import sys

from app import create_app

app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    default_port = "5000" if sys.platform.startswith("win") else "8000"
    port = int(os.getenv("PORT", default_port))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
