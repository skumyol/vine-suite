FROM python:3.11-slim

WORKDIR /app

# Memory optimization environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Limit OpenCV/OpenMP threads to save memory
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    VECLIB_MAXIMUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2 \
    # OCR settings
    ENABLED_ENGINES=easyocr,tesseract,paddle \
    GC_AFTER_REQUEST=true \
    MAX_CONCURRENT_REQUESTS=3

# Install system dependencies for OCR (layered for caching)
# Using --network=host equivalent for build by adding DNS servers directly
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && update-ca-certificates && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy service code
COPY config.py .
COPY main.py .
COPY evaluation.py .

EXPOSE 8082

# Memory-optimized: Single worker, limit concurrent connections
# Each request gets exclusive access to engines (no lock contention)
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8082", \
     "--workers", "1", \
     "--limit-concurrency", "3", \
     "--backlog", "10", \
     "--timeout-keep-alive", "5"]
