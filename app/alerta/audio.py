import math
import shutil
import subprocess
import struct
import threading

from app.alerta.talk import ip_da_camera

MENSAGEM_PADRAO = "Atenção, pessoa detectada na área de risco"

SAMPLE_RATE = 16000
# Um frame AAC tem 1024 amostras: 1024 / 16000 Hz = 64 ms. O envio precisa
# acontecer nesse ritmo; com 20 ms o áudio sai ~3x rápido e a câmera engasga.
FRAME_MS = 64
# Silêncio no começo: a câmera corta o início do áudio.
ATRASO_INICIAL_MS = 150

_cache_audio = {}
_cache_lock = threading.Lock()

def _ffmpeg_para_aac(entrada, dados=None):
    """Converte para AAC ADTS 16 kHz mono (com silêncio inicial).

    `entrada` são os argumentos de entrada do ffmpeg; `dados` vão pelo stdin
    quando a entrada é pipe:0."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não está instalado (no Docker: apt-get install ffmpeg)")
    comando = [
        "ffmpeg", "-y", "-loglevel", "error", *entrada,
        "-af", f"adelay={ATRASO_INICIAL_MS}:all=1",
        "-ar", str(SAMPLE_RATE), "-ac", "1",
        "-c:a", "aac", "-b:a", "64k", "-f", "adts", "pipe:1",
    ]
    r = subprocess.run(comando, input=dados, capture_output=True, timeout=30)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("ffmpeg falhou: " + r.stderr.decode(errors="replace"))
    return r.stdout


def _e_adts_16k_mono(dados):
    """True se `dados` já é AAC/ADTS 16 kHz mono (não precisa converter)."""
    if len(dados) < 7 or dados[0] != 0xFF or (dados[1] & 0xF6) != 0xF0:
        return False
    indice_freq = (dados[2] >> 2) & 0x0F
    canais = ((dados[2] & 0x01) << 2) | (dados[3] >> 6)
    return indice_freq == 8 and canais == 1  # 8 = 16000 Hz


def _audio_de_arquivo(caminho):
    with open(caminho, "rb") as f:
        dados = f.read()
    if _e_adts_16k_mono(dados):
        return dados
    return _ffmpeg_para_aac(["-i", caminho])

def gerar_voz(mensagem):
    wav = subprocess.run(
        ["espeak-ng", "-v", "pt-br", "-s", "170", "--stdout", mensagem],
        capture_output=True, timeout=30, check=True,
    ).stdout
    return _ffmpeg_para_aac(["-f", "wav", "-i", "pipe:0"], wav)

def gerar_bip():
    segundos, freq, amplitude = 1.0, 880.0, 0.25
    pcm = bytearray()
    for i in range(int(segundos * SAMPLE_RATE)):
        pcm.extend(struct.pack("<h", int(32767 * amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))))
    entrada = ["-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "pipe:0"]
    return _ffmpeg_para_aac(entrada, bytes(pcm))

def obter_audio(cfg):
    """Áudio da câmera, pronto para enviar. Gera uma vez e guarda em cache.

    Ordem: arquivo "audio" -> voz da "mensagem_alerta" (espeak-ng) -> bip."""
    caminho = cfg.get("audio")
    mensagem = cfg.get("mensagem_alerta", MENSAGEM_PADRAO)
    chave = (caminho, mensagem)

    with _cache_lock:
        if chave in _cache_audio:
            return _cache_audio[chave]

        audio = None
        if caminho:
            try:
                audio = _audio_de_arquivo(caminho)
            except Exception as e:
                print(f"[ÁUDIO] Não consegui usar {caminho!r} ({e}). Usando a mensagem.")
        if audio is None:
            try:
                audio = gerar_voz(mensagem)
            except Exception as e:
                print(f"[ÁUDIO] Não consegui gerar a voz ({e}). Usando bip.")
                audio = gerar_bip()

        _cache_audio[chave] = audio
        return audio


def preparar_audios(cameras):
    """Prepara o áudio de cada câmera na partida, para o primeiro alerta
    não pagar o custo de arquivo/ffmpeg."""
    for cfg in cameras:
        if not ip_da_camera(cfg):
            continue
        origem = cfg.get("audio") or repr(cfg.get("mensagem_alerta", MENSAGEM_PADRAO))
        print(f"[ÁUDIO] Preparando áudio de {cfg['nome']}: {origem}")
        try:
            obter_audio(cfg)
        except Exception as e:
            print(f"[ÁUDIO] {cfg['nome']}: falhou ({type(e).__name__}: {e})")