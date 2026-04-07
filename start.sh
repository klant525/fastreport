#!/usr/bin/env sh
set -eu

exec gunicorn -c gunicorn.conf.py server:app
