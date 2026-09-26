import json

CAMINHO_CONFIG = "config.json"

def carregar_config():
    with open(CAMINHO_CONFIG, "r") as f:
        return json.load(f)

def salvar_config(config):
    with open(CAMINHO_CONFIG, "w") as f:
        json.dump(config, f, indent=2)