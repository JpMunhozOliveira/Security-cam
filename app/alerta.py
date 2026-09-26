import subprocess

def tocar_alerta(nome_camera):
    print(f"[ALERTA] Pessoa entrou na zona de perigo! Câmera: {nome_camera}")
    mensagem = "Atenção, pessoa detectada na área de risco"
    subprocess.Popen(["espeak-ng", "-v", "pt-br", mensagem])