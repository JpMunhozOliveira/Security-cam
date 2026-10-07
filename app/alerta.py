"""Alerta sonoro: fala pelo alto-falante da câmera Imou (talk) e, se não der,
usa o espeak-ng local como fallback.

Campos opcionais no config.json, por câmera:

    {
      "nome": "Portao",
      "url": "rtsp://...",
      "zona": [0, 0, 100, 100],
      "serial": "DPE0003777172",        <- liga o áudio pela câmera
      "usuario": "admin",               <- (padrão: admin)
      "senha": "...",                   <- (padrão: variável IMOU_RTSP_PASSWORD)
      "mensagem_alerta": "Atenção, pessoa detectada na área de risco",
      "som_local": false,               <- true = toca também no PC
      "relay": true,                    <- false = tenta conexão P2P direta
      "track1": 0, "track2": 0          <- só mexa se a câmera recusar o áudio
    }

Sem "serial" a câmera não fala e só toca o espeak-ng local.

Teste isolado (fala na primeira câmera do config.json):

    python -m app.alerta
    python -m app.alerta --camera Portao --debug
"""

import asyncio
import math
import os
import shutil
import socket
import struct
import subprocess
import threading
import time
from argparse import Namespace
from contextlib import suppress

MENSAGEM_PADRAO = "Atenção, pessoa detectada na área de risco"

SAMPLE_RATE = 16000
# Um frame AAC tem 1024 amostras: 1024 / 16000 Hz = 64 ms. O envio precisa
# acontecer nesse ritmo; com 20 ms o áudio sai ~3x rápido e a câmera engasga.
FRAME_MS = 64

_cache_audio = {}
_cache_lock = threading.Lock()
_camera_ocupada = {}
_ocupada_lock = threading.Lock()


# --------------------------------------------------------------------------
# Geração do áudio (AAC/ADTS, 16 kHz, mono)
# --------------------------------------------------------------------------

def _para_aac(entrada, formato_entrada):
    """Converte áudio (bytes) para AAC ADTS 16 kHz mono usando o ffmpeg."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não está instalado (no Docker: apt-get install ffmpeg)")
    comando = ["ffmpeg", "-y", "-loglevel", "error", "-f", formato_entrada]
    if formato_entrada == "s16le":
        comando += ["-ar", str(SAMPLE_RATE), "-ac", "1"]
    comando += [
        "-i", "pipe:0",
        # 0,3 s de silêncio no começo: a câmera corta o início do áudio
        "-af", "adelay=300:all=1",
        "-ar", str(SAMPLE_RATE), "-ac", "1",
        "-c:a", "aac", "-b:a", "64k", "-f", "adts", "pipe:1",
    ]
    r = subprocess.run(comando, input=entrada, capture_output=True, timeout=30)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("ffmpeg falhou: " + r.stderr.decode(errors="replace"))
    return r.stdout


def gerar_bip():
    segundos, freq, amplitude = 1.0, 880.0, 0.25
    total = int(segundos * SAMPLE_RATE)
    pcm = bytearray()
    for i in range(total):
        valor = int(32767 * amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        pcm.extend(struct.pack("<h", valor))
    return _para_aac(bytes(pcm), "s16le")


def gerar_voz(mensagem):
    wav = subprocess.run(
        ["espeak-ng", "-v", "pt-br", "-s", "150", "--stdout", mensagem],
        capture_output=True, timeout=30, check=True,
    ).stdout
    return _para_aac(wav, "wav")


def obter_audio(mensagem):
    """Gera o áudio uma vez por mensagem e guarda em cache."""
    with _cache_lock:
        if mensagem in _cache_audio:
            return _cache_audio[mensagem]
        try:
            audio = gerar_voz(mensagem)
        except Exception as e:
            print(f"[ALERTA] Não consegui gerar a voz ({e}). Usando bip.")
            audio = gerar_bip()
        _cache_audio[mensagem] = audio
        return audio


# --------------------------------------------------------------------------
# Áudio pela câmera (túnel P2P + visualtalk)
# --------------------------------------------------------------------------

def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _falar_sincrono(porta, usuario, senha, audio, cfg=None, host="127.0.0.1"):
    from app.imou_visualtalk import VisualTalkClient

    cfg = cfg or {}
    cliente = None
    for tentativa in range(10):
        try:
            cliente = VisualTalkClient(
                host, porta,
                username=usuario, password=senha,
                nonce=None, created=None,
                password_digest_override=None, lightweight_digest=None,
                timeout=15.0,
            )
            break
        except OSError:
            time.sleep(0.3)
    if cliente is None:
        raise RuntimeError(f"não consegui conectar em {host}:{porta}")

    args = Namespace(
        channel=1, subtype=0, encrypt=3,
        track1=cfg.get("track1", 0), track2=cfg.get("track2", 0),
        talk_track=64, media_track=5,
        sdp=None, open_only=False,
        codec="aac-adts", sample_rate=SAMPLE_RATE, frame_ms=FRAME_MS,
    )
    try:
        print("[ALERTA] Enviando comandos de inicialização do áudio...")
        for resposta in cliente.start_talk(args):
            print(f"[ALERTA] Resposta VisualTalk: {resposta.code} {resposta.status_line}")
            if resposta.code >= 400:
                raise RuntimeError(f"câmera recusou o áudio: {resposta.status_line}")

        frames = cliente.send_audio(audio, args)
        time.sleep(0.5)  # deixa a câmera terminar de tocar o final
        return frames
    finally:
        with suppress(OSError):
            cliente.sock.shutdown(socket.SHUT_RDWR)
        cliente.close()

async def _falar_na_camera(cfg, audio, debug=False):
    serial = cfg["serial"]
    usuario = cfg.get("usuario", "admin")
    senha = cfg.get("senha") or os.environ.get("IMOU_RTSP_PASSWORD")
    if not senha:
        raise RuntimeError("sem senha: defina IMOU_RTSP_PASSWORD ou 'senha' na câmera")

    ip = cfg.get("ip")
    if ip:
        try:
            print(f"[ALERTA] Conexão direta em {ip}:8086 (sem P2P)")
            return await asyncio.to_thread(
                _falar_sincrono, int(cfg.get("porta", 8086)), usuario, senha, audio, cfg, ip
            )
        except Exception as e:
            print(f"[ALERTA] Direto falhou ({type(e).__name__}: {e}); tentando P2P.")

    print("[ALERTA] Iniciando handshake P2P...")
    from app.imou_dhp2p import DHP2PTunnel, p2p_handshake

    ptcp = await p2p_handshake(
        serial,
        relay_mode=cfg.get("relay", True),
        dtype=0, username=usuario, password=senha, debug=debug,
    )

    print("[ALERTA] Handshake P2P concluído.")

    tunel = DHP2PTunnel(ptcp, 8086, debug=debug)
    porta = _porta_livre()

    print(f"[ALERTA] Iniciando túnel local na porta {porta}...")

    tarefa = asyncio.create_task(tunel.start("127.0.0.1", porta))
    try:
        print("[ALERTA] Aguardando túnel...")
        await asyncio.sleep(0.8)
        print("[ALERTA] Iniciando VisualTalk...")
        return await asyncio.to_thread(_falar_sincrono, porta, usuario, senha, audio, cfg)
    
    finally:
        tarefa.cancel()
        # não espera para sempre o túnel encerrar
        await asyncio.wait({tarefa}, timeout=3)
        if tarefa.done() and not tarefa.cancelled():
            tarefa.exception()  # marca como lida (evita aviso de exceção não tratada)


def falar_na_camera(cfg, audio, debug=False, timeout=120):
    return asyncio.run(asyncio.wait_for(_falar_na_camera(cfg, audio, debug), timeout))


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
        if cfg.get("serial"):
            try:
                audio = obter_audio(mensagem)
                frames = falar_na_camera(cfg, audio)
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
    """Dispara o alerta sem bloquear o loop de detecção."""
    cfg = camera_config or {}
    mensagem = cfg.get("mensagem_alerta", MENSAGEM_PADRAO)
    print(f"[ALERTA] Pessoa entrou na zona de perigo! Câmera: {nome_camera}")

    with _ocupada_lock:
        if _camera_ocupada.get(nome_camera):
            return  # ainda falando o alerta anterior
        _camera_ocupada[nome_camera] = True

    threading.Thread(
        target=_executar_alerta, args=(nome_camera, cfg, mensagem), daemon=True
    ).start()


# --------------------------------------------------------------------------
# Teste manual: python -m app.alerta
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    from app.config import carregar_config

    p = argparse.ArgumentParser()
    p.add_argument("--camera", help="nome da câmera no config.json (padrão: a primeira com serial)")
    p.add_argument("--debug", action="store_true")
    a = p.parse_args()

    cameras = [c for c in carregar_config()["cameras"] if c.get("serial")]
    if a.camera:
        cameras = [c for c in cameras if c["nome"] == a.camera]
    if not cameras:
        raise SystemExit("Nenhuma câmera com 'serial' no config.json.")

    cam = cameras[0]
    msg = cam.get("mensagem_alerta", MENSAGEM_PADRAO)
    print(f"Gerando áudio: {msg!r}")
    audio = obter_audio(msg)
    print(f"Conectando em {cam['nome']} ({cam['serial']})...")
    frames = falar_na_camera(cam, audio, debug=a.debug)
    print(f"Enviado! {frames} frames DHAV.")