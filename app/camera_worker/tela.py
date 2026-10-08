import cv2

class Janela:
    """Janela opcional com a detecção e a zona desenhadas."""

    def __init__(self, nome, zona):
        self.nome = nome
        self.zona = [int(v) for v in zona]
        self.ativa = False        # já exibiu pelo menos um frame
        self._desativada = False  # falhou ao abrir; segue sem tela

    def _clique(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"[{self.nome}] Clique: x={x}, y={y}")

    def mostrar(self, results, pessoa_detectada):
        """Desenha e exibe o frame. Retorna False se o usuário apertou 'q'."""
        if self._desativada:
            return True
        try:
            frame = results[0].plot()
            x1, y1, x2, y2 = self.zona
            cor = (0, 0, 255) if pessoa_detectada else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 2)
            cv2.imshow(self.nome, frame)

            if not self.ativa:
                cv2.setMouseCallback(self.nome, self._clique)
                self.ativa = True

            return cv2.waitKey(1) & 0xFF != ord("q")
        except cv2.error as e:
            print(f"[{self.nome}] Não consegui abrir a janela ({e}). Seguindo sem tela.")
            self._desativada = True
            self.ativa = False
            return True

    def aguardar(self, ms=10):
        """Mantém a janela viva enquanto não há frame. False = apertou 'q'."""
        return cv2.waitKey(ms) & 0xFF != ord("q")

    def fechar(self):
        if self.ativa:
            cv2.destroyWindow(self.nome)