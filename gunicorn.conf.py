import os


bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "1"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")
timeout = int(os.getenv("GUNICORN_TIMEOUT", "150"))
graceful_timeout = 20
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "1"))
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "12"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "3"))
preload_app = False
worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR", "/dev/shm")
accesslog = "-"
errorlog = "-"
capture_output = True
