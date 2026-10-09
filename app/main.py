import os
import signal
import threading
import time
import traceback

from app.alerta.audio import preparar_audios
from app.camera_worker.worker import processar_camera
from app.config import carregar_config

ESPERA_REINICIO = 5    # segundos antes de reiniciar uma câmera que caiu
ESPERA_ENCERRAR = 12   # tempo máximo esperando as câmeras fecharem ao encerrar


def rodar_camera(camera_config, parar):
    """Roda uma câmera e a reinicia se ela cair por uma exceção.

    Se o processar_camera terminar normalmente (tecla 'q' ou encerramento),
    não reinicia."""
    nome = camera_config.get("nome", "?")

    while not parar.is_set():
        try:
            processar_camera(camera_config, parar)
            return
        except Exception:
            print(f"[MAIN] {nome}: a câmera caiu com erro:")
            traceback.print_exc()
            print(f"[MAIN] {nome}: reiniciando em {ESPERA_REINICIO}s...")
            parar.wait(ESPERA_REINICIO)


def instalar_sinais(parar):
    """Ctrl+C (SIGINT) e docker stop (SIGTERM) pedem um encerramento limpo.
    Um segundo sinal força a saída imediata."""

    def tratar(signum, _frame):
        if parar.is_set():
            print("[MAIN] Novo sinal recebido: saindo agora.", flush=True)
            os._exit(1)
        print(f"[MAIN] {signal.Signals(signum).name} recebido; encerrando...", flush=True)
        parar.set()

    signal.signal(signal.SIGINT, tratar)
    signal.signal(signal.SIGTERM, tratar)


def main():
    parar = threading.Event()
    instalar_sinais(parar)

    cameras = carregar_config()["cameras"]

    print("[MAIN] Preparando áudios das câmeras...")
    preparar_audios(cameras)

    if parar.is_set():
        return

    threads = []
    for camera_config in cameras:
        nome = camera_config.get("nome", "?")
        t = threading.Thread(target=rodar_camera, args=(camera_config, parar),
                             name=f"camera-{nome}", daemon=True)
        t.start()
        threads.append(t)

    # Espera até pedirem para parar ou todas as câmeras terminarem sozinhas.
    while not parar.is_set() and any(t.is_alive() for t in threads):
        parar.wait(0.5)

    parar.set()
    limite = time.monotonic() + ESPERA_ENCERRAR
    for t in threads:
        t.join(timeout=max(0.0, limite - time.monotonic()))

    presas = [t.name for t in threads if t.is_alive()]
    if presas:
        print(f"[MAIN] Não terminaram a tempo (saindo mesmo assim): {', '.join(presas)}")
    print("[MAIN] Encerrado.")


if __name__ == "__main__":
    main()