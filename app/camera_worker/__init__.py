"""Worker de câmera: captura RTSP numa thread, YOLO e verificação de zona.

As variáveis do OpenCV precisam ser definidas ANTES de qualquer import do
cv2, por isso ficam aqui, no topo do pacote.
"""

import os

os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|analyzeduration;1000000|probesize;1000000"
)

from app.camera_worker.worker import processar_camera  # noqa: E402

__all__ = ["processar_camera"]