import time


class Metricas:
    """Acumula tempos do YOLO/zona e imprime os relatórios."""

    def __init__(self, nome, stream):
        self.nome = nome
        self.stream = stream

        self.inicio = time.monotonic()
        self._ultimo_relatorio = self.inicio

        self.processados = 0     # frames que rodaram o YOLO
        self.sem_movimento = 0   # frames dispensados pelo filtro de movimento
        self.deteccoes = 0

        self._total_yolo = 0.0
        self.max_yolo = 0.0
        self._total_zona = 0.0
        self._total_espera = 0.0
        self.max_espera = 0.0

    # ---- registro ------------------------------------------------------

    def registrar_yolo(self, segundos):
        self._total_yolo += segundos
        self.max_yolo = max(self.max_yolo, segundos)

    def registrar_espera(self, segundos):
        """Tempo esperando a vez no YOLO compartilhado."""
        self._total_espera += segundos
        self.max_espera = max(self.max_espera, segundos)

    def registrar_zona(self, segundos, pessoa_detectada):
        self._total_zona += segundos
        if pessoa_detectada:
            self.deteccoes += 1

    # ---- cálculo -------------------------------------------------------

    def _calcular(self):
        decorrido = time.monotonic() - self.inicio
        n = self.processados
        analisados = n + self.sem_movimento
        return {
            "tempo": decorrido,
            "fps_captura": self.stream.frames_recebidos / decorrido if decorrido > 0 else 0,
            "fps_proc": n / decorrido if decorrido > 0 else 0,
            "yolo_ms": self._total_yolo / n * 1000 if n else 0,
            "zona_ms": self._total_zona / n * 1000 if n else 0,
            "espera_ms": self._total_espera / n * 1000 if n else 0,
            "economia": self.sem_movimento / analisados * 100 if analisados else 0,
        }

    # ---- relatórios ----------------------------------------------------

    def relatorio_se_hora(self, intervalo):
        agora = time.monotonic()
        if agora - self._ultimo_relatorio < intervalo:
            return
        self._ultimo_relatorio = agora
        self.imprimir_parcial()

    def imprimir_parcial(self):
        m, n, s = self._calcular(), self.nome, self.stream
        print()
        print(f"[{n}] ===== MÉTRICAS =====")
        print(f"[{n}] Tempo de teste: {m['tempo']:.1f}s")
        print(f"[{n}] Abertura RTSP: {s.tempo_abertura or 0:.2f}s")
        print(f"[{n}] Frames recebidos: {s.frames_recebidos}")
        print(f"[{n}] FPS captura: {m['fps_captura']:.2f}")
        print(f"[{n}] Frames pulados (pular_frames): {s.frames_ignorados}")
        print(f"[{n}] Frames com YOLO: {self.processados}")
        print(f"[{n}] Frames sem movimento (YOLO dispensado): {self.sem_movimento} ({m['economia']:.0f}%)")
        print(f"[{n}] FPS do YOLO: {m['fps_proc']:.2f}")
        print(f"[{n}] YOLO médio: {m['yolo_ms']:.2f} ms")
        print(f"[{n}] YOLO máximo: {self.max_yolo * 1000:.2f} ms")
        print(f"[{n}] Espera do YOLO (média/máx): {m['espera_ms']:.2f} / {self.max_espera * 1000:.2f} ms")
        print(f"[{n}] Zona média: {m['zona_ms']:.2f} ms")
        print(f"[{n}] Pessoas detectadas: {self.deteccoes}")
        print(f"[{n}] Reconexões: {s.reconexoes}")
        print(f"[{n}] =====================")

    def imprimir_final(self):
        m, s = self._calcular(), self.stream
        print()
        print("=" * 60)
        print(f"[{self.nome}] RESULTADO FINAL")
        print("=" * 60)
        print(f"Tempo total:              {m['tempo']:.2f}s")
        print(f"Abertura RTSP:            {s.tempo_abertura or 0:.2f}s")
        print(f"Frames recebidos:         {s.frames_recebidos}")
        print(f"FPS médio da captura:     {m['fps_captura']:.2f}")
        print(f"Frames pulados:           {s.frames_ignorados}")
        print(f"Frames com YOLO:          {self.processados}")
        print(f"Frames sem movimento:     {self.sem_movimento} ({m['economia']:.0f}%)")
        print(f"FPS médio do YOLO:        {m['fps_proc']:.2f}")
        print(f"YOLO médio:               {m['yolo_ms']:.2f} ms")
        print(f"YOLO máximo:              {self.max_yolo * 1000:.2f} ms")
        print(f"Espera do YOLO (média):   {m['espera_ms']:.2f} ms")
        print(f"Espera do YOLO (máxima):  {self.max_espera * 1000:.2f} ms")
        print(f"Zona média:               {m['zona_ms']:.2f} ms")
        print(f"Pessoas detectadas:       {self.deteccoes}")
        print(f"Reconexões:               {s.reconexoes}")
        print("=" * 60)
        print(f"[{self.nome}] Encerrado.")