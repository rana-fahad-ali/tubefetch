# TubeFetch - production image
FROM python:3.12-slim

# ffmpeg is needed to merge HD video+audio and to make MP3s
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates

# Cloud hosts (Render, Railway, HF Spaces...) hand us the port via $PORT
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 600
