import threading

from app.config import carregar_config
from app.camera_worker import processar_camera

def main():
    config = carregar_config()
    cameras = config["cameras"]

    threads = []
    for camera_config in cameras:
        t = threading.Thread(target=processar_camera, args=(camera_config,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()