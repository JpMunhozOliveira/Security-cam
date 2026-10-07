"""Teste rápido do áudio pela câmera, sem rodar o programa inteiro.

Rode da pasta que contém a pasta app/ (a mesma do config.json):

    python teste_alerta.py                      # fala a mensagem na 1ª câmera com serial
    python teste_alerta.py --camera Portao      # escolhe a câmera pelo nome
    python teste_alerta.py --bip                # manda só um bip (isola problema de voz)
    python teste_alerta.py --mensagem "Teste"   # outra frase
    python teste_alerta.py --debug              # log detalhado do P2P
    python teste_alerta.py --completo           # usa o mesmo caminho do app (tocar_alerta)
    python teste_alerta.py --serial DPE... --senha ...   # sem config.json
    python teste_alerta.py --track1 6           # variações se a câmera recusar o áudio
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import alerta  # noqa: E402


def checar(ok, texto):
    print(("  [ok]   " if ok else "  [FALTA] ") + texto)
    return bool(ok)


def main():
    p = argparse.ArgumentParser(description="Teste do áudio pela câmera Imou")
    p.add_argument("--camera", help="nome da câmera no config.json")
    p.add_argument("--serial")
    p.add_argument("--usuario")
    p.add_argument("--senha")
    p.add_argument("--mensagem")
    p.add_argument("--bip", action="store_true", help="envia só um bip")
    p.add_argument("--no-relay", action="store_true", help="tenta P2P direto em vez de relay")
    p.add_argument("--track1", type=int)
    p.add_argument("--track2", type=int)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--completo", action="store_true", help="passa por tocar_alerta, como no app")
    a = p.parse_args()

    # ---- monta a config da câmera ----
    cfg = {}
    if not a.serial:
        try:
            from app.config import carregar_config
            cams = [c for c in carregar_config()["cameras"] if c.get("serial")]
            if a.camera:
                cams = [c for c in cams if c.get("nome") == a.camera]
            if cams:
                cfg = dict(cams[0])
        except FileNotFoundError:
            print("config.json não encontrado nesta pasta (use --serial/--senha ou rode da pasta certa).")
    if a.serial:
        cfg["serial"] = a.serial
    if a.usuario:
        cfg["usuario"] = a.usuario
    if a.senha:
        cfg["senha"] = a.senha
    if a.no_relay:
        cfg["relay"] = False
    if a.track1 is not None:
        cfg["track1"] = a.track1
    if a.track2 is not None:
        cfg["track2"] = a.track2
    cfg.setdefault("nome", "teste")

    mensagem = a.mensagem or cfg.get("mensagem_alerta", alerta.MENSAGEM_PADRAO)
    senha = cfg.get("senha") or os.environ.get("IMOU_RTSP_PASSWORD")

    # ---- pré-requisitos ----
    print("Pré-requisitos:")
    ok = checar(shutil.which("ffmpeg"), "ffmpeg instalado")
    if not a.bip:
        checar(shutil.which("espeak-ng"), "espeak-ng instalado (sem ele, vira bip)")
    ok &= checar(cfg.get("serial"), f"serial da câmera ({cfg.get('serial', 'não definido')})")
    ok &= checar(senha, "senha (IMOU_RTSP_PASSWORD ou campo 'senha')")
    if not ok:
        sys.exit("\nResolva o que está faltando acima e rode de novo.")

    # ---- áudio ----
    print(f"\nGerando áudio ({'bip' if a.bip else repr(mensagem)})...")
    t0 = time.time()
    audio = alerta.gerar_bip() if a.bip else alerta.obter_audio(mensagem)
    print(f"  {len(audio)} bytes AAC em {time.time() - t0:.1f}s")

    # ---- envio ----
    if a.completo:
        print("\nDisparando via tocar_alerta (igual ao app)...")
        alerta._cache_audio[mensagem] = audio
        cfg["mensagem_alerta"] = mensagem
        alerta.tocar_alerta(cfg["nome"], cfg)
        time.sleep(0.5)
        while alerta._camera_ocupada.get(cfg["nome"]):
            time.sleep(0.3)
        print("Terminou. Veja acima se apareceu 'áudio enviado à câmera' ou 'usando som local'.")
        return

    print(f"\nConectando via P2P ({'relay' if cfg.get('relay', True) else 'direto'}), pode levar uns segundos...")
    t0 = time.time()
    try:
        frames = alerta.falar_na_camera(cfg, audio, debug=a.debug)
    except Exception as e:
        print(f"\nFALHOU em {time.time() - t0:.1f}s: {type(e).__name__}: {e}")
        print("Dicas: rode com --debug; tente --track1 6; tente --no-relay; confira serial e senha.")
        sys.exit(1)
    print(f"\nEnviado! {frames} frames em {time.time() - t0:.1f}s.")
    print("Se você ouviu o som na câmera, está tudo certo.")


if __name__ == "__main__":
    main()
