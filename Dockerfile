# Pin Debian 12. The moving `3.11-slim` tag now targets Debian 13, which can
# change the C runtime underneath TensorFlow without any repository change.
FROM python:3.11-slim-bookworm

WORKDIR /app

# Render runs this service on a CPU. Disable oneDNN's optimized kernels to
# avoid the native allocator crash observed during TensorFlow startup.
# Unbuffered output makes each startup checkpoint appear in Render's logs
# immediately, which makes import and model-loading failures distinguishable.
ENV TF_ENABLE_ONEDNN_OPTS=0 \
    PYTHONUNBUFFERED=1

# OpenCV needs these graphics libraries even in headless mode.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["python", "app.py"]
