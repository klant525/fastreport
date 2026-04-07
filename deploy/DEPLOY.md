# FastReport VPS 1GB

Recommended stack for a 1GB RAM VPS:

1. Python venv + `requirements.txt`
2. `gunicorn` with `1` worker
3. `nginx` in front for rate limiting
4. system package `tesseract-ocr`

Recommended runtime values on 1GB RAM:

- `WEB_CONCURRENCY=1`
- `GUNICORN_THREADS=1`
- `GUNICORN_TIMEOUT=150`
- keep GPT mode optional

## Ubuntu Quick Start

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx tesseract-ocr
sudo mkdir -p /opt/fastreport
sudo chown -R $USER:$USER /opt/fastreport
cd /opt/fastreport
git clone https://github.com/klant525/fastreport.git .
cp .env.local .env.local.backup 2>/dev/null || true
bash deploy/deploy.sh
sudo cp deploy/nginx-fastreport.conf /etc/nginx/sites-available/fastreport
sudo ln -sf /etc/nginx/sites-available/fastreport /etc/nginx/sites-enabled/fastreport
sudo nginx -t
sudo systemctl reload nginx
```

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Verify OCR binary:

```bash
tesseract --version
```

## Run

```bash
cp deploy/fastreport.service /etc/systemd/system/fastreport.service
sudo systemctl daemon-reload
sudo systemctl enable --now fastreport
```

Use [deploy/nginx-fastreport.conf](/opt/fastreport/deploy/nginx-fastreport.conf) as the nginx site config.

## If You Use OpenAI Vision

Create `.env.local` in the app root:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_VISION_ENABLED=1
OPENAI_VISION_MODEL=gpt-4.1-mini
SITE_URL=https://your-domain.com
COOKIE_SECURE=1
```

Notes:

- Keep `WEB_CONCURRENCY=1` on 1GB RAM.
- Keep OCR requests small. The app already limits to 12 images and removes temp files.
- Prefer nginx over Caddy on 1GB if you want built-in rate limiting without extra plugins.
- Do not increase worker count unless you also increase VPS RAM.
- This repo no longer targets Windows OCR setup.
