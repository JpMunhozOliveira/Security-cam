import time

from app.alerta import tocar_alerta
from app.camera_worker.config import TEMPO_RELATORIO
from app.camera_worker.metricas import Metricas
from app.camera_worker.modelo import detectar, obter_modelo
from app.camera_worker.movimento import FiltroMovimento
from app.camera_worker.stream import CameraStream
from app.camera_worker.tela import Janela
from app.deteccao import pessoa_na_zona

ESPERA_FRAME_S = 0.1          # quanto dorme esperando um frame novo
ESPERA_FRAME_JANELA_S = 0.01  # com janela aberta, precisa tratar o teclado


def _pessoa_na_zona(results, zona, modo):
    for caixa in results[0].boxes.xyxy:
        if pessoa_na_zona(tuple(caixa.tolist()), zona, modo):
            return True
    return False


def processar_camera(camera_config):
    nome = camera_config["nome"]
    url = camera_config["url"]
    zona = camera_config["zona"]
    modo = camera_config.get("modo_deteccao", "pes")
    mostrar_tela = camera_config.get("mostrar_tela", False)
    alertar = camera_config.get("alertar", True)

    pular_n = 1
    if camera_config.get("pular_frames", True):
        pular_n = max(int(camera_config.get("quantidade_pular_frames", 2)), 1)

    filtro = None
    if camera_config.get("filtro_movimento", False):
        filtro = FiltroMovimento(
            zona,
            fracao_minima=camera_config.get("movimento_fracao", 0.01),
            manter_s=camera_config.get("movimento_manter_s", 2.0),
        )

    print()
    print("=" * 60)
    print(f"[{nome}] TESTE DE GARGALO")
    print(f"[{nome}] URL: {url}")
    print(f"[{nome}] pular_n={pular_n}  filtro_movimento={'sim' if filtro else 'não'}")
    print("=" * 60)

    obter_modelo()  # carrega e aquece uma vez; as outras câmeras reaproveitam

    stream = CameraStream(nome, url, pular_n).start()
    metricas = Metricas(nome, stream)
    janela = Janela(nome, zona) if mostrar_tela else None
    ultimo_id = 0

    def janela_pediu_para_sair():
        return bool(janela and janela.ativa and not janela.aguardar(1))

    try:
        while True:
            metricas.relatorio_se_hora(TEMPO_RELATORIO)

            espera = ESPERA_FRAME_JANELA_S if (janela and janela.ativa) else ESPERA_FRAME_S
            ultimo_id, frame = stream.ler_novo(ultimo_id, timeout=espera)

            if frame is None:
                if janela_pediu_para_sair():
                    break
                continue

            # Filtro de movimento: dispensa o YOLO em cena parada
            if filtro and not filtro.precisa_yolo(frame):
                metricas.sem_movimento += 1
                if janela_pediu_para_sair():
                    break
                continue

            metricas.processados += 1

            # YOLO (modelo compartilhado)
            try:
                results, espera_yolo, inferencia = detectar(frame)
            except Exception as e:
                print(f"[{nome}] Erro no YOLO: {type(e).__name__}: {e}")
                time.sleep(1)
                continue
            metricas.registrar_yolo(inferencia)
            metricas.registrar_espera(espera_yolo)

            if filtro and len(results[0].boxes) > 0:
                filtro.registrar_pessoa()

            # Zona
            inicio = time.monotonic()
            pessoa_detectada = _pessoa_na_zona(results, zona, modo)
            metricas.registrar_zona(time.monotonic() - inicio, pessoa_detectada)

            if pessoa_detectada and alertar:
                tocar_alerta(nome, camera_config)  # não bloqueia; respeita o intervalo

            if janela and not janela.mostrar(results, pessoa_detectada):
                break
    finally:
        stream.stop()
        if janela:
            janela.fechar()

    metricas.imprimir_final()