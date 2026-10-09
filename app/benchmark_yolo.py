"""Benchmark do YOLO: PyTorch x OpenVINO x ONNX, em frames reais.

Roda o mesmo conjunto de frames (de um vídeo ou de um RTSP) em cada formato e
compara latência, FPS e quantidade de pessoas detectadas.

Uso (dentro do container; openvino/onnx são instalados só para o teste):

    docker compose run --rm camera-app sh -c \
      "pip install -q openvino onnx onnxruntime && \
       python -m app.benchmark_yolo --video app/testes/video.mp4"

Opções úteis:
    --frames 150      quantos frames medir
    --passo 2         usa 1 frame a cada 2 do vídeo (cobre mais do vídeo)
    --formatos pytorch openvino onnx
    --threads 4       limita as threads do PyTorch
    --imgsz 320       igual ao IMGSZ do app

Os modelos exportados (yolov8n_openvino_model/, yolov8n.onnx) são gravados ao
lado do yolov8n.pt; estão no .gitignore.
"""

import argparse
import math
import time

import cv2
import numpy as np
from ultralytics import YOLO

CLASSE_PESSOA = 0
FORMATOS = ("pytorch", "openvino", "onnx")


def carregar_frames(fonte, quantidade, passo):
    cap = cv2.VideoCapture(fonte)
    if not cap.isOpened():
        raise SystemExit(f"Não consegui abrir a fonte: {fonte}")
    frames, lidos = [], 0
    while len(frames) < quantidade:
        ok, frame = cap.read()
        if not ok:
            break
        if lidos % passo == 0:
            frames.append(frame)
        lidos += 1
    cap.release()
    return frames


def forma_letterbox(altura, largura, imgsz, stride=32):
    """Tamanho (alt, larg) que o ultralytics usa no PyTorch para este frame.
    Os modelos exportados são fixados nesse mesmo tamanho, para a comparação
    ser justa (senão o exportado processaria 320x320 contra 320x192)."""
    r = imgsz / max(altura, largura)
    return (
        math.ceil(round(altura * r) / stride) * stride,
        math.ceil(round(largura * r) / stride) * stride,
    )


def preparar(formato, modelo_pt, imgsz, forma):
    """Retorna (modelo, imgsz a usar na inferência)."""
    base = YOLO(modelo_pt)
    if formato == "pytorch":
        return base, imgsz
    inicio = time.perf_counter()
    caminho = base.export(format=formato, imgsz=list(forma))
    print(f"  exportado em {time.perf_counter() - inicio:.1f}s -> {caminho}")
    return YOLO(str(caminho), task="detect"), list(forma)


def medir(modelo, frames, imgsz, aquecer):
    for i in range(aquecer):
        modelo(frames[i % len(frames)], imgsz=imgsz, classes=[CLASSE_PESSOA], verbose=False)

    total, inferencia = [], []
    pessoas = frames_com_pessoa = 0
    for frame in frames:
        t0 = time.perf_counter()
        r = modelo(frame, imgsz=imgsz, classes=[CLASSE_PESSOA], verbose=False)
        total.append((time.perf_counter() - t0) * 1000)
        inferencia.append(r[0].speed.get("inference", 0.0))
        n = len(r[0].boxes)
        pessoas += n
        frames_com_pessoa += 1 if n else 0

    total = np.array(total)
    return {
        "media": total.mean(),
        "mediana": float(np.median(total)),
        "p95": float(np.percentile(total, 95)),
        "max": total.max(),
        "inferencia": float(np.mean(inferencia)),
        "fps": 1000 / total.mean(),
        "pessoas": pessoas,
        "frames_com_pessoa": frames_com_pessoa,
    }


def imprimir_tabela(resultados, n_frames):
    base = resultados.get("pytorch")
    print()
    print(f"Resultados ({n_frames} frames; tempos em ms, por frame completo = pré + inferência + pós)")
    print("-" * 92)
    print(f"{'formato':<10}{'média':>8}{'mediana':>9}{'p95':>8}{'máx':>8}{'infer.':>8}{'FPS':>8}{'ganho':>8}{'pessoas':>9}{'frames c/':>10}")
    print("-" * 92)
    for formato, r in resultados.items():
        ganho = f"{base['media'] / r['media']:.2f}x" if base else "-"
        print(f"{formato:<10}{r['media']:>8.1f}{r['mediana']:>9.1f}{r['p95']:>8.1f}{r['max']:>8.1f}"
              f"{r['inferencia']:>8.1f}{r['fps']:>8.1f}{ganho:>8}{r['pessoas']:>9}{r['frames_com_pessoa']:>10}")
    print("-" * 92)

    if not base:
        return
    print()
    for formato, r in resultados.items():
        if formato == "pytorch":
            continue
        ganho = base["media"] / r["media"]
        if ganho >= 1.5:
            print(f"- {formato}: {ganho:.2f}x mais rápido. Vale levar para o app.")
        elif ganho >= 1.15:
            print(f"- {formato}: {ganho:.2f}x. Ganho moderado; só compensa com várias câmeras.")
        else:
            print(f"- {formato}: {ganho:.2f}x. Sem ganho relevante; fique com o PyTorch.")
        ref = base["pessoas"]
        if ref and abs(r["pessoas"] - ref) / ref > 0.10:
            print(f"  ATENÇÃO: {formato} detectou {r['pessoas']} pessoas contra {ref} do PyTorch "
                  f"(diferença > 10%). Confira a precisão antes de trocar.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", required=True, help="arquivo de vídeo ou URL RTSP")
    p.add_argument("--modelo", default="yolov8n.pt")
    p.add_argument("--imgsz", type=int, default=320)
    p.add_argument("--frames", type=int, default=150)
    p.add_argument("--passo", type=int, default=1)
    p.add_argument("--aquecer", type=int, default=10)
    p.add_argument("--formatos", nargs="+", choices=FORMATOS, default=list(FORMATOS))
    p.add_argument("--threads", type=int, default=0, help="threads do PyTorch (0 = padrão)")
    a = p.parse_args()

    frames = carregar_frames(a.video, a.frames, max(a.passo, 1))
    if not frames:
        raise SystemExit("Nenhum frame lido da fonte.")

    altura, largura = frames[0].shape[:2]
    forma = forma_letterbox(altura, largura, a.imgsz)
    print(f"{len(frames)} frames de {largura}x{altura}; entrada do modelo: {forma[1]}x{forma[0]} (imgsz={a.imgsz})")

    if a.threads:
        import torch

        torch.set_num_threads(a.threads)
        print(f"PyTorch limitado a {a.threads} threads")

    resultados = {}
    for formato in a.formatos:
        print(f"\n[{formato}] preparando...")
        try:
            modelo, imgsz = preparar(formato, a.modelo, a.imgsz, forma)
            print(f"[{formato}] medindo...")
            resultados[formato] = medir(modelo, frames, imgsz, a.aquecer)
        except Exception as e:
            print(f"[{formato}] FALHOU: {type(e).__name__}: {e}")

    if not resultados:
        raise SystemExit("Nenhum formato funcionou.")
    imprimir_tabela(resultados, len(frames))


if __name__ == "__main__":
    main()