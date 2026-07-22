FROM python:3.11-slim

# System dependencies for PyMuPDF, WeasyPrint, PaddleOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libc-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download PaddleOCR models (will be cached)
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en', show_log=False)"

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY pyproject.toml .
COPY pyproject.toml .

# Install package in development mode
RUN pip install -e .

# Create data directories
RUN mkdir -p /app/data/{koperasi_profiles,regulatory_chunks,templates,synthetic_docs,eval/{ground_truth,test_documents}}

# Default command
CMD ["python", "-m", "halal_koperasi_agent.cli", "--help"]