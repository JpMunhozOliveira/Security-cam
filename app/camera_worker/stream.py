import threading
import time

import cv2

from app.camera_worker.config import (
    ABERTURA_TIMEOUT_MS,
    ESPERA_MAX,
    ESPERA_MIN,
    LEITURA_TIMEOUT_MS,
    SEM_FRAME_SEGUNDOS,
    TIMEOUT_STOP_S,
)


class CameraStream:
    """Lê o stream numa thread própria e guarda apenas o frame mais recente.

    `pular_n` = 1 entrega todos os frames; N > 1 entrega 1 a cada N. Os
    frames pulados só são decodificados (grab), sem a conversão para BGR
    (retrieve), o que poupa CPU."""

    def __init__(self, nome, url, pular_n=1):
        self.nome = nome
        self.url = url
        self.pular_n = max(int(pular_n), 1)

        self._frame = None
        self._frame_id = 0
        self._cond = threading.Condition()
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

        # Métricas da captura
        self.frames_recebidos = 0   # todos os frames que a câmera entregou
        self.frames_ignorados = 0   # pulados por pular_n (sem retrieve)
        self.conexoes = 0
        self.tempo_abertura = None
        self.tempo_ultimo_frame = 0
        self.tempo_primeiro_frame = None

    @property
    def reconexoes(self):
        """Conexões além da primeira."""
        return max(self.conexoes - 1, 0)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._parar.set()
        with self._cond:
            self._cond.notify_all()
        self._thread.join(timeout=TIMEOUT_STOP_S)

    def ler_novo(self, ultimo_id, timeout=0):
        """Retorna (id, frame) se houver frame novo; senão (ultimo_id, None).

        Com `timeout` > 0, dorme até chegar um frame novo (ou o tempo acabar),
        em vez de o chamador ficar consultando em loop."""
        with self._cond:
            if timeout and self._frame_id == ultimo_id and not self._parar.is_set():
                self._cond.wait_for(
                    lambda: self._frame_id != ultimo_id or self._parar.is_set(),
                    timeout,
                )
            if self._frame is None or self._frame_id == ultimo_id:
                return ultimo_id, None
            return self._frame_id, self._frame

    def _criar_captura(self):
        """VideoCapture com timeouts de abertura e leitura (OpenCV >= 4.5.2)."""
        try:
            return cv2.VideoCapture(
                self.url,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, ABERTURA_TIMEOUT_MS,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, LEITURA_TIMEOUT_MS,
                ],
            )
        except (TypeError, AttributeError):
            print(f"[{self.nome}] OpenCV sem suporte a timeouts; usando o padrão.")
            return cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

    def _abrir(self):
        try:
            cap = self._criar_captura()
            if not cap.isOpened():
                cap.release()
                return None
            return cap
        except Exception as e:
            print(f"[{self.nome}] Erro ao abrir stream: {type(e).__name__}: {e}")
            return None

    def _guardar_frame(self, frame):
        with self._cond:
            self._frame = frame
            self._frame_id += 1
            self._cond.notify_all()

    def _ler_ate_falhar(self, cap):
        """Lê frames até parar, falhar por muito tempo ou ser encerrado."""
        ultimo_ok = time.monotonic()

        while not self._parar.is_set():
            if cap.grab():
                agora = time.monotonic()
                if self.tempo_primeiro_frame is None:
                    self.tempo_primeiro_frame = agora
                self.tempo_ultimo_frame = agora
                self.frames_recebidos += 1
                ultimo_ok = agora

                if self.frames_recebidos % self.pular_n == 0:
                    ret, frame = cap.retrieve()
                    if ret:
                        self._guardar_frame(frame)
                else:
                    self.frames_ignorados += 1
                continue

            if time.monotonic() - ultimo_ok > SEM_FRAME_SEGUNDOS:
                print(f"[{self.nome}] Sem imagem há {SEM_FRAME_SEGUNDOS}s. Reconectando...")
                return

            self._parar.wait(0.1)

    def _loop(self):
        espera = ESPERA_MIN

        while not self._parar.is_set():
            inicio = time.monotonic()
            cap = self._abrir()

            if cap is None:
                print(f"[{self.nome}] Não consegui abrir o stream. Nova tentativa em {espera}s...")
                self._parar.wait(espera)
                espera = min(espera * 2, ESPERA_MAX)
                continue

            self.tempo_abertura = time.monotonic() - inicio
            self.conexoes += 1
            print(f"[{self.nome}] Câmera conectada! Abertura: {self.tempo_abertura:.3f}s")
            espera = ESPERA_MIN

            try:
                self._ler_ate_falhar(cap)
            except Exception as e:
                print(f"[{self.nome}] Erro no stream: {type(e).__name__}: {e}. Reconectando...")
            finally:
                cap.release()