FROM python:3.11-slim

# Instala dependências do sistema que o OpenCV precisa (incluindo suporte gráfico, pra debug visual)
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
    fontconfig \
    fonts-dejavu-core \
    espeak-ng \
    ffmpeg \
    pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Instala o PyTorch e o torchvision juntos, na versão só-CPU (garante que as versões sejam compatíveis)
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Instala as bibliotecas Python listadas no requirements.txt
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia o código e a configuração para dentro do container
COPY app/ ./app/
COPY teste_alerta.py .
COPY config.json .

CMD ["python", "-u", "-m", "app.main"]