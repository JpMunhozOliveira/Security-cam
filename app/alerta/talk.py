import socket
import time
from contextlib import suppress
from urllib.parse import urlparse

PORTA_PADRAO = 8086
TIMEOUT_SOCKET = 5.0   # na LAN a resposta é quase instantânea
TENTATIVAS = 2         # nova conexão se a câmera não abrir o talk
ESPERA_ENTRE_TENTATIVAS = 2.0


def ip_da_camera(cfg):
    """IP do config; se não houver, tenta extrair da URL RTSP."""
    if cfg.get("ip"):
        return cfg["ip"]
    if cfg.get("url"):
        return urlparse(cfg["url"]).hostname
    return None


def fechar_cliente(cliente):
    # shutdown() antes do close(): a thread de "drain" do cliente fica presa
    # em recv(), e sem isso o FIN só sai depois do timeout do socket.
    with suppress(OSError):
        cliente.sock.shutdown(socket.SHUT_RDWR)
    with suppress(OSError):
        cliente.close()


def abrir_talk(ip, porta, usuario, senha, cfg):
    """Conecta e abre a sessão de talk. Em caso de falha, tenta de novo com
    uma conexão NOVA (nunca reaproveita a anterior)."""
    from app.protocolo.imou_visualtalk import VisualTalkClient

    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        cliente = None
        try:
            cliente = VisualTalkClient(ip, porta, username=usuario, password=senha,
                                       timeout=TIMEOUT_SOCKET)
            respostas = cliente.start_talk(track1=cfg.get("track1", 0), track2=cfg.get("track2", 0))
            print("[ALERTA] VisualTalk: " + ", ".join(str(r.code) for r in respostas))
            return cliente
        except Exception as e:
            ultimo_erro = e
            if cliente is not None:
                fechar_cliente(cliente)
            print(f"[ALERTA] Tentativa {tentativa}/{TENTATIVAS} falhou: {type(e).__name__}: {e}")
            if tentativa < TENTATIVAS:
                time.sleep(ESPERA_ENTRE_TENTATIVAS)
    raise RuntimeError(f"não consegui abrir o talk em {ip}:{porta} ({ultimo_erro})")