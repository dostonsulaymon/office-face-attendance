FROM python:3.11-slim

# OpenCV (headless) still needs glib + libgomp at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only torch first (from the dedicated index), then the rest.
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Vendored Silent-Face-Anti-Spoofing (src + pretrained models) and our wrapper.
COPY vendor/src ./vendor/src
COPY vendor/resources ./vendor/resources
COPY predictor.py app.py ./

EXPOSE 8902
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8902"]
