"""Alerta sonoro: fala pelo alto-falante da câmera Imou (VisualTalk direto
pela rede local, porta 8086) e, se não der, usa o espeak-ng local.

Campos no config.json, por câmera:

    {
      "nome": "Frente",
      "url": "rtsp://admin:senha@10.0.2.194:554/...",
      "zona": [0, 0, 100, 100],
      "ip": "10.0.2.194",               <- liga o áudio pela câmera
                                           (se faltar, usa o IP da "url")
      "usuario": "admin",               <- (padrão: admin)
      "senha": "...",                   <- (padrão: variável IMOU_RTSP_PASSWORD)
      "porta": 8086,                    <- (padrão: 8086)
      "audio": "app/audios/bem_vindo.aac",  <- áudio pronto (wav, mp3, aac...)
      "mensagem_alerta": "Seja bem-vindo",  <- usada só se não houver "audio"
                                               (ou se o arquivo falhar) e no som local
      "som_local": false,               <- true = toca também no PC
      "track1": 0, "track2": 0          <- só mexa se a câmera recusar o áudio
    }

Áudio pronto: um .aac em ADTS 16 kHz mono é enviado como está (já deve ter o
silêncio inicial). Qualquer outro formato (wav, mp3, m4a, aac com outra taxa)
é convertido uma vez, na partida, pelo ffmpeg, já com o silêncio inicial.

Para gerar um .aac a partir de um texto (uma vez só):

    python -m app.alerta --gerar "Seja bem-vindo" --saida app/audios/bem_vindo.aac

Teste isolado (fala na primeira câmera do config.json):

    python -m app.alerta
    python -m app.alerta --camera Frente
"""

import os
import argparse

from app.alerta.audio import gerar_voz, obter_audio
from app.alerta.controle import falar_na_camera
from app.alerta.talk import ip_da_camera
from app.config import carregar_config

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--camera", help="nome da câmera no config.json (padrão: a primeira)")
    p.add_argument("--gerar", metavar="TEXTO", help="gera um .aac a partir do texto e sai")
    p.add_argument("--saida", default="app/audios/alerta.aac", help="destino do --gerar")
    a = p.parse_args()

    if a.gerar:
        os.makedirs(os.path.dirname(a.saida) or ".", exist_ok=True)
        with open(a.saida, "wb") as f:
            f.write(gerar_voz(a.gerar))
        raise SystemExit(f"Áudio salvo em {a.saida}. Use no config: \"audio\": \"{a.saida}\"")

    cameras = carregar_config()["cameras"]
    if a.camera:
        cameras = [c for c in cameras if c["nome"] == a.camera]
    if not cameras:
        raise SystemExit("Câmera não encontrada no config.json.")

    cam = cameras[0]

    print(f"Preparando áudio de {cam['nome']}...")
    audio = obter_audio(cam)

    print(f"Falando em {cam['nome']} ({ip_da_camera(cam)})...")
    frames = falar_na_camera(cam, audio)

    print(f"Enviado! {frames} frames DHAV.")