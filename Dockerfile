FROM python:3.11-slim

# Instala dependências do sistema que o OpenCV precisa (incluindo suporte gráfico)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xfixes0 \
    libx11-6 \
    libxext6 \
    libsm6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala as bibliotecas Python
RUN pip install ultralytics opencv-python

# Copia o código para dentro do container
COPY detect.py .

CMD ["python", "detect.py"]