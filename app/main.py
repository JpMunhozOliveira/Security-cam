import threading
import time
import traceback

from app.alerta.audio import preparar_audios
from app.camera_worker.worker import processar_camera
from app.config import carregar_config

ESPERA_REINICIO = 5  # segundos antes de reiniciar uma câmera que caiu


def rodar_camera(camera_config):
    """Roda uma câmera e a reinicia se ela cair por uma exceção.

    Se o processar_camera terminar normalmente (ex.: tecla 'q' na janela),
    não reinicia."""
    nome = camera_config.get("nome", "?")

    while True:
        try:
            processar_camera(camera_config)
            return
        except Exception:
            print(f"[MAIN] {nome}: a câmera caiu com erro:")
            traceback.print_exc()
            print(f"[MAIN] {nome}: reiniciando em {ESPERA_REINICIO}s...")
            time.sleep(ESPERA_REINICIO)


def main():
    cameras = carregar_config()["cameras"]

    print("[MAIN] Preparando áudios das câmeras...")
    preparar_audios(cameras)

    threads = []
    for camera_config in cameras:
        t = threading.Thread(target=rodar_camera, args=(camera_config,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()