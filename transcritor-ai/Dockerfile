# CPU (funciona em qualquer VPS). Para GPU NVIDIA, troque a base por
# nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 (+ python3-pip) e rode com --gpus all.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY transcritor ./transcritor

# Modelos ficam num volume para não baixar de novo a cada deploy
ENV TRANSCRITOR_MODELS_DIR=/modelos \
    PYTHONUNBUFFERED=1
VOLUME ["/modelos", "/dados"]
EXPOSE 8000

# Em servidor exposto, defina TRANSCRITOR_TOKEN (docker run -e TRANSCRITOR_TOKEN=...)
CMD ["python", "-m", "transcritor", "servidor", "--host", "0.0.0.0", "--porta", "8000", "--dados", "/dados"]
