from ultralytics import YOLO
import cv2

# Carrega o modelo já treinado (baixa automaticamente na primeira vez)
model = YOLO('yolov8n.pt')  # 'n' = nano, o mais leve/rápido

# Endereço do stream da câmera do celular (troque pelo seu IP, se mudar)
url = "http://192.168.1.7:8080/video"

cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Não consegui abrir o stream da câmera. Confere se o app está rodando e se o IP está certo.")

# Só processa 1 a cada N frames (ajuste esse número conforme necessário)
PULAR_FRAMES = 3
contador = 0

# Guarda o último resultado desenhado, pra mostrar nos frames "pulados"
ultimo_frame_anotado = None

while True:
    ret, frame = cap.read()
    if not ret:
        print("Não recebi frame da câmera. Tentando de novo...")
        continue

    contador += 1

    if contador % PULAR_FRAMES == 0:
        # Roda a detecção só nesse frame
        results = model(frame, classes=[0])  # classe 0 = "person" no COCO
        ultimo_frame_anotado = results[0].plot()

        if len(results[0].boxes) > 0:
            print("Pessoa detectada!")
    else:
        # Nos frames pulados, reaproveita o último resultado (ou mostra cru, se ainda não tem nenhum)
        ultimo_frame_anotado = frame if ultimo_frame_anotado is None else ultimo_frame_anotado

    cv2.imshow("Camera", ultimo_frame_anotado)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()