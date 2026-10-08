import os

TEMPO_RELATORIO = 10       # imprime métricas a cada X segundos
SEM_FRAME_SEGUNDOS = 20    # sem imagem por tanto tempo -> reconecta
ABERTURA_TIMEOUT_MS = 30000  # abrir o RTSP (hoje leva ~12,5 s)
LEITURA_TIMEOUT_MS = 8000    # cap.read() sem frame (maior que o GOP da câmera)
TIMEOUT_STOP_S = 7           # espera máxima da thread ao encerrar
ESPERA_MIN = 2             # backoff da reconexão
ESPERA_MAX = 30

MODELO_YOLO = "yolov8n.pt"
IMGSZ = 320
CLASSE_PESSOA = 0

# Threads do PyTorch (CPU). 0/ausente = padrão do PyTorch (todos os núcleos).
# Teste valores como 2 ou 4 com a variável de ambiente TORCH_THREADS.
TORCH_THREADS = int(os.environ.get("TORCH_THREADS", "0")) or None