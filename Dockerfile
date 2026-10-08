FROM python:3.11-slim

# Instala dependências do sistema que o OpenCV precisa
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xfixes0 \
    libxext6 \
    libsm6 \
    libxrender1 \
    fontconfig \
    fonts-dejavu-core \
    espeak-ng \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Instala o PyTorch e o torchvision juntos, na versão só-CPU
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Instala as bibliotecas Python listadas no requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baixa o modelo YOLO uma vez, durante o build
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copia o código e a configuração para dentro do container
COPY app/ ./app/

# Set Python environment variables to prevent memory bloat
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MALLOC_TRIM_THRESHOLD_=128000 \
    MALLOC_MMAP_THRESHOLD_=131072

CMD ["python", "-u", "-m", "app.main"]
