import os
import subprocess
import threading
import time

from app.alerta.audio import FRAME_MS, MENSAGEM_PADRAO, SAMPLE_RATE, obter_audio
from app.alerta.talk import PORTA_PADRAO, abrir_talk, fechar_cliente, ip_da_camera

INTERVALO_PADRAO = 30  # segundos entre alertas da mesma câmera (0 = sem limite)

_camera_ocupada = {}
_ultimo_alerta = {}
_ocupada_lock = threading.Lock()


def falar_na_camera(cfg, audio):
    """Envia o áudio ao alto-falante da câmera. Retorna o nº de frames."""
    ip = ip_da_camera(cfg)
    if not ip:
        raise RuntimeError("sem 'ip' no config da câmera")

    usuario = cfg.get("usuario", "admin")
    senha = cfg.get("senha") or os.environ.get("IMOU_RTSP_PASSWORD")
    if not senha:
        raise RuntimeError("sem senha: defina IMOU_RTSP_PASSWORD ou 'senha' na câmera")

    porta = int(cfg.get("porta", PORTA_PADRAO))

    inicio = time.monotonic()
    cliente = abrir_talk(ip, porta, usuario, senha, cfg)
    print(f"[ALERTA] Talk aberto em {time.monotonic() - inicio:.2f}s")
    try:
        frames = cliente.send_audio(audio, sample_rate=SAMPLE_RATE, frame_ms=FRAME_MS)
        time.sleep(0.5)  # deixa a câmera terminar de tocar o final
        return frames
    finally:
        fechar_cliente(cliente)


# --------------------------------------------------------------------------
# Fallback local
# --------------------------------------------------------------------------

def _falar_local(mensagem):
    try:
        subprocess.Popen(["espeak-ng", "-v", "pt-br", mensagem])
    except FileNotFoundError:
        print("[ALERTA] espeak-ng não encontrado; sem som local.")


# --------------------------------------------------------------------------
# API usada pelo camera_worker
# --------------------------------------------------------------------------

def _executar_alerta(nome_camera, cfg, mensagem):
    try:
        if ip_da_camera(cfg):
            try:
                frames = falar_na_camera(cfg, obter_audio(cfg))
                print(f"[ALERTA] {nome_camera}: áudio enviado à câmera ({frames} frames).")
                if cfg.get("som_local", False):
                    _falar_local(mensagem)
                return
            except Exception as e:
                print(f"[ALERTA] {nome_camera}: falha no áudio da câmera: {type(e).__name__}: {e}")
                print(f"[ALERTA] {nome_camera}: usando som local.")
        _falar_local(mensagem)
    finally:
        with _ocupada_lock:
            _camera_ocupada[nome_camera] = False


def tocar_alerta(nome_camera, camera_config=None):
    """Dispara o alerta sem bloquear o loop de detecção.

    Ignora o disparo se a câmera ainda está falando ou se o último alerta dela
    começou há menos de `intervalo_alerta` segundos (padrão 30; 0 = sem limite)."""
    cfg = camera_config or {}
    mensagem = cfg.get("mensagem_alerta", MENSAGEM_PADRAO)
    intervalo = float(cfg.get("intervalo_alerta", INTERVALO_PADRAO))
    agora = time.monotonic()

    with _ocupada_lock:
        if _camera_ocupada.get(nome_camera):
            return  # ainda falando o alerta anterior
        ultimo = _ultimo_alerta.get(nome_camera)
        if intervalo > 0 and ultimo is not None and agora - ultimo < intervalo:
            return  # alerta recente; espera o intervalo
        _camera_ocupada[nome_camera] = True
        _ultimo_alerta[nome_camera] = agora

    print(f"[ALERTA] Pessoa na zona de perigo! Câmera: {nome_camera}")
    threading.Thread(
        target=_executar_alerta, args=(nome_camera, cfg, mensagem), daemon=True
    ).start()