"""YOLO compartilhado: carregado e aquecido uma vez, usado por todas as câmeras.

O modelo do ultralytics guarda estado interno e não aceita inferências
simultâneas, então as chamadas são serializadas por um lock. Funciona com
threads (uma por câmera) no mesmo processo.
"""

import threading
import time

import numpy as np
from ultralytics import YOLO

from app.camera_worker.config import CLASSE_PESSOA, IMGSZ, MODELO_YOLO, TORCH_THREADS

_modelo = None
_lock_carga = threading.Lock()
_lock_inferencia = threading.Lock()


def _aquecer(modelo, rodadas=3):
    """Frames pretos para o primeiro frame real não pagar a inicialização."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    inicio = time.monotonic()
    for _ in range(rodadas):
        modelo(frame, imgsz=IMGSZ, classes=[CLASSE_PESSOA], verbose=False)
    print(f"[YOLO] Aquecido em {time.monotonic() - inicio:.3f}s")


def obter_modelo():
    """Carrega e aquece o modelo na primeira chamada; depois só devolve."""
    global _modelo
    with _lock_carga:
        if _modelo is None:
            if TORCH_THREADS:
                import torch

                torch.set_num_threads(TORCH_THREADS)
                print(f"[YOLO] PyTorch limitado a {TORCH_THREADS} threads")
            inicio = time.monotonic()
            modelo = YOLO(MODELO_YOLO)
            print(f"[YOLO] {MODELO_YOLO} carregado em {time.monotonic() - inicio:.3f}s")
            _aquecer(modelo)
            _modelo = modelo
        return _modelo


def detectar(frame):
    """Roda o YOLO no frame. Retorna (results, espera_s, inferencia_s).

    `espera_s` é o tempo esperando a vez (outras câmeras usando o modelo);
    `inferencia_s` é só o tempo do YOLO."""
    modelo = obter_modelo()

    t0 = time.monotonic()
    with _lock_inferencia:
        t1 = time.monotonic()
        results = modelo(frame, imgsz=IMGSZ, classes=[CLASSE_PESSOA], verbose=False)
        t2 = time.monotonic()

    return results, t1 - t0, t2 - t1