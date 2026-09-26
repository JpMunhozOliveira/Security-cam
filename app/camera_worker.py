import os
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"

import cv2
import time
from ultralytics import YOLO

from app.deteccao import pessoa_na_zona
from app.alerta import tocar_alerta

TEMPO_ENTRE_ALERTAS = 30
INTERVALO_HEARTBEAT = 10

def processar_camera(camera_config):
    nome = camera_config["nome"]
    url = camera_config["url"]
    zona = camera_config["zona"]
    modo_deteccao = camera_config.get("modo_deteccao", "pes")
    pular_frames = camera_config.get("pular_frames", True)
    quantidade_pular_frames = camera_config.get("quantidade_pular_frames", 3)
    mostrar_tela = camera_config.get("mostrar_tela", False)

    print(f"Iniciando câmera: {nome} ({url})")

    model = YOLO('yolov8n.pt')
    cap = cv2.VideoCapture(url)

    if not cap.isOpened():
        print(f"[{nome}] Não consegui abrir o stream da câmera.")
        return

    print(f"[{nome}] Câmera conectada! Monitorando...")

    contador = 0
    ultimo_heartbeat = time.time()
    ultimo_alerta = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"[{nome}] Não recebi frame. Tentando de novo...")
            time.sleep(1)
            continue

        contador += 1

        if time.time() - ultimo_heartbeat > INTERVALO_HEARTBEAT:
            print(f"[{nome}] Ainda monitorando... ({contador} frames lidos)")
            ultimo_heartbeat = time.time()

        if pular_frames and contador % quantidade_pular_frames != 0:
            continue

        results = model(frame, classes=[0], verbose=False)

        pessoa_detectada = False
        for caixa in results[0].boxes.xyxy:
            x1, y1, x2, y2 = caixa.tolist()
            if pessoa_na_zona((x1, y1, x2, y2), zona, modo_deteccao):
                pessoa_detectada = True
                break

        if pessoa_detectada:
            agora = time.time()
            if agora - ultimo_alerta > TEMPO_ENTRE_ALERTAS:
                tocar_alerta(nome)
                ultimo_alerta = agora

        if mostrar_tela:
            frame_anotado = results[0].plot()
            zx1, zy1, zx2, zy2 = [int(v) for v in zona]
            cor = (0, 0, 255) if pessoa_detectada else (0, 255, 0)
            cv2.rectangle(frame_anotado, (zx1, zy1), (zx2, zy2), cor, 2)
            cv2.imshow(nome, frame_anotado)

            def mostrar_coordenadas(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    print(f"[{nome}] Você clicou em: x={x}, y={y}")

            cv2.setMouseCallback(nome, mostrar_coordenadas)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break