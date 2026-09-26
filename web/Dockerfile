FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

RUN pip install flask opencv-python-headless

COPY app.py .
COPY templates/ ./templates/

CMD ["python", "-u", "app.py"]