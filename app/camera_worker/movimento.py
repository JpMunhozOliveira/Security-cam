"""Filtro de movimento: decide se vale rodar o YOLO neste frame.

Compara, em escala reduzida, o recorte da zona (mais uma margem) com o frame
anterior. O YOLO roda quando:
  - houve movimento no recorte, ou
  - houve movimento / pessoa detectada nos últimos `manter_s` segundos
    (cobre quem entra e fica parado), ou
  - já se passaram `forcar_s` segundos sem rodar (rede de segurança).
"""

import time

import cv2
import numpy as np

_NUNCA = float("-inf")


class FiltroMovimento:
    def __init__(self, zona, *, margem=0.15, lado=96, limiar_pixel=20,
                 fracao_minima=0.01, manter_s=2.0, forcar_s=1.0):
        x1, y1, x2, y2 = zona
        self.zona = (int(min(x1, x2)), int(min(y1, y2)), int(max(x1, x2)), int(max(y1, y2)))
        self.margem = margem
        self.lado = lado
        self.limiar_pixel = limiar_pixel      # diferença mínima (0-255) por pixel
        self.fracao_minima = fracao_minima    # fração de pixels mudados = movimento
        self.manter_s = manter_s
        self.forcar_s = forcar_s

        self._anterior = None
        self._ultimo_movimento = _NUNCA
        self._ultima_pessoa = _NUNCA
        self._ultimo_yolo = _NUNCA

    def _recorte(self, frame):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = self.zona
        mx = int((x2 - x1) * self.margem)
        my = int((y2 - y1) * self.margem)
        x1, y1 = max(0, x1 - mx), max(0, y1 - my)
        x2, y2 = min(w, x2 + mx), min(h, y2 + my)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    def _mudou(self, frame):
        recorte = self._recorte(frame)
        if recorte is None:  # zona fora do frame: não filtra
            return True

        cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
        pequeno = cv2.resize(cinza, (self.lado, self.lado), interpolation=cv2.INTER_AREA)
        pequeno = cv2.GaussianBlur(pequeno, (5, 5), 0)

        anterior, self._anterior = self._anterior, pequeno
        if anterior is None:
            return True

        diferenca = cv2.absdiff(pequeno, anterior)
        mudados = np.count_nonzero(diferenca > self.limiar_pixel)
        return mudados / diferenca.size >= self.fracao_minima

    def precisa_yolo(self, frame):
        """True se o YOLO deve rodar neste frame."""
        agora = time.monotonic()
        if self._mudou(frame):
            self._ultimo_movimento = agora

        rodar = (
            agora - self._ultimo_movimento < self.manter_s
            or agora - self._ultima_pessoa < self.manter_s
            or agora - self._ultimo_yolo >= self.forcar_s
        )
        if rodar:
            self._ultimo_yolo = agora
        return rodar

    def registrar_pessoa(self):
        """Chame quando o YOLO viu alguém (em qualquer lugar da imagem)."""
        self._ultima_pessoa = time.monotonic()