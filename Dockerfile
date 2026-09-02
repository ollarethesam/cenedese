# Dev image for the home server. Code is bind-mounted at runtime (see
# compose.yaml), so nothing is COPYed in but the dependency manifest.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# collectstatic is not optional: STORAGES uses WhiteNoise's manifest storage, so
# {% static %} raises unless the manifest exists — even with DEBUG on.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py runserver 0.0.0.0:8000"]
