#!/usr/bin/env bash
# Render build command. Installs deps, gathers static files, applies migrations.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
