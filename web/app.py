from flask import Flask, render_template, request, redirect, url_for, Response
import cv2
import json
import os

app = Flask(__name__)

CAMINHO_CONFIG = "config.json"

def carregar_config():
    if not os.path.exists(CAMINHO_CONFIG):
        return {"cameras": []}
    with open(CAMINHO_CONFIG, "r") as f:
        return json.load(f)

def salvar_config(config):
    with open(CAMINHO_CONFIG, "w") as f:
        json.dump(config, f, indent=2)

@app.route("/")
def index():
    config = carregar_config()
    return render_template("index.html", cameras=config["cameras"])

@app.route("/adicionar", methods=["POST"])
def adicionar():
    config = carregar_config()
    nova_camera = {
        "nome": request.form["nome"],
        "url": request.form["url"],
        "zona": [50, 50, 200, 200],
        "modo_deteccao": "pes",
        "pular_frames": True,
        "quantidade_pular_frames": 3,
        "mostrar_tela": False
    }
    config["cameras"].append(nova_camera)
    salvar_config(config)
    return redirect(url_for("index"))

@app.route("/remover/<int:indice>", methods=["POST"])
def remover(indice):
    config = carregar_config()
    if 0 <= indice < len(config["cameras"]):
        config["cameras"].pop(indice)
        salvar_config(config)
    return redirect(url_for("index"))

@app.route("/editar/<int:indice>")
def editar(indice):
    config = carregar_config()
    camera = config["cameras"][indice]
    return render_template("editar.html", camera=camera, indice=indice)

@app.route("/salvar/<int:indice>", methods=["POST"])
def salvar(indice):
    config = carregar_config()
    camera = config["cameras"][indice]

    camera["zona"] = [
        int(request.form["x1"]),
        int(request.form["y1"]),
        int(request.form["x2"]),
        int(request.form["y2"]),
    ]
    camera["modo_deteccao"] = request.form["modo_deteccao"]
    camera["pular_frames"] = "pular_frames" in request.form
    camera["quantidade_pular_frames"] = int(request.form["quantidade_pular_frames"])

    salvar_config(config)
    return redirect(url_for("index"))

@app.route("/snapshot/<int:indice>")
def snapshot(indice):
    config = carregar_config()
    camera = config["cameras"][indice]

    cap = cv2.VideoCapture(camera["url"])
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return "Não consegui pegar imagem da câmera", 500

    ok, buffer = cv2.imencode(".jpg", frame)
    return Response(buffer.tobytes(), mimetype="image/jpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)