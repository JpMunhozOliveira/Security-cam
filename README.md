[⬅ Voltar](https://github.com/JpMunhozOliveira)

# 📹 Sistema de Monitoramento Inteligente

<p align="center"> <a href="#"> <img src="https://skillicons.dev/icons?i=python,docker,linux" alt="Python, Docker, Linux" /> </a> </p>

<p align="center"> <a href="#"> <img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV" /> </a>
  <a href="#"> <img src="https://img.shields.io/badge/Ultralytics%20YOLO-111F68?style=for-the-badge&logoColor=white" alt="Ultralytics YOLO" /> </a>
  <a href="#"> <img src="https://img.shields.io/badge/FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white" alt="FFmpeg" /> </a>
  <a href="#"> <img src="https://img.shields.io/badge/RTSP-Video%20Streaming-333333?style=for-the-badge" alt="RTSP" /> </a> </p>

Sistema de monitoramento por câmeras IP com detecção de pessoas em zonas de interesse e emissão de alertas sonoros diretamente na câmera.

O projeto utiliza **Python, OpenCV e YOLO** para analisar imagens em tempo real, identificar pessoas e acionar alertas por meio do protocolo de comunicação das câmeras compatíveis.

> 🚧 **Status:** em desenvolvimento. O foco atual está na estabilidade da captura de vídeo, no desempenho da detecção e na redução da latência dos alertas.

## ✨ Funcionalidades

* **Detecção de pessoas:** utiliza YOLO para identificar pessoas nas imagens capturadas.
* **Monitoramento por zonas:** verifica se uma pessoa está em uma região de interesse configurada.
* **Múltiplas câmeras:** permite configurar e processar câmeras de forma independente.
* **Captura em paralelo:** utiliza threads para separar a leitura do vídeo do processamento das imagens.
* **Reconexão automática:** tenta restabelecer a captura quando o fluxo de vídeo apresenta falhas.
* **Alertas sonoros:** gera mensagens de voz ou utiliza arquivos de áudio personalizados.
* **Comunicação local:** envia áudio diretamente para câmeras compatíveis pela rede local, utilizando VisualTalk/DHAV.
* **Execução em Docker:** permite executar o sistema em um ambiente de aplicação conteinerizado.

## 🛠️ Tecnologias utilizadas

| Tecnologia              | Finalidade                          |
| ----------------------- | ----------------------------------- |
| Python                  | Lógica principal da aplicação       |
| YOLO (Ultralytics)      | Detecção de pessoas                 |
| OpenCV                  | Captura e processamento de imagens  |
| FFmpeg                  | Conversão e preparação de áudio     |
| eSpeak NG               | Geração de voz sintetizada          |
| RTSP                    | Recepção do fluxo de vídeo          |
| TCP / VisualTalk / DHAV | Comunicação de áudio com as câmeras |
| Docker                  | Isolamento e execução da aplicação  |

## 🏗️ Arquitetura

O sistema é dividido em módulos para separar a captura de vídeo, a detecção e a comunicação com as câmeras.

```text
Câmera IP
    │
    ├── RTSP
    │    ↓
    │  Captura de vídeo
    │    ↓
    │  OpenCV
    │    ↓
    │  YOLO
    │    ↓
    │  Verificação da zona
    │
    └── VisualTalk / DHAV
             ↑
       Controle de alertas
             ↑
       Geração de áudio
```

### Organização do projeto

```text
Camera-Seguranca/
├── app/
│   ├── alerta/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── audio.py
│   │   ├── controle.py
|   |   └── talk.py
│   ├── audios/
│   ├── camera_worker/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── metricas.py
│   │   ├── modelo.py
│   │   ├── movimento.py
│   │   ├── stream.py
│   │   ├── tela.py
│   │   ├── worker.py
│   ├── protocolo/
│   │   ├── __init__.py
│   │   ├── imou_visualtalk.py
│   │   ├── imou_dhav.py
│   │   └── imou_wsse.py
│   ├── __init__.py
│   ├── benchmark_yolo.py
│   ├── config.py
│   ├── deteccao.py
│   └── main.py
├── config.json
├── Dockerfile
└── docker-compose.yml
```

*Observação: a estrutura acima representa a organização prevista para o projeto. Os nomes e caminhos devem ser ajustados caso a estrutura atual do repositório seja diferente.*

## ⚙️ Configuração

As câmeras são configuradas no arquivo `config.json`, que reúne informações de conexão, zonas de detecção e parâmetros de monitoramento.

Exemplo ilustrativo:

```json
{
  "cameras": [
    {
      "nome": "Frente",
      "ip": "192.168.1.100",
      "url": "rtsp://USUARIO:SENHA@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1",
      "zona": [100, 100, 500, 400],
      "modo_deteccao": "pes",
      "pular_frames": true,
      "quantidade_pular_frames": 2,
      "mostrar_tela": false,
      "tempo_entre_alertas": 30,
      "mensagem_alerta": "Atenção, pessoa detectada na área de risco"
    }
  ]
}
```

Os valores são exemplos e devem ser adaptados à câmera, à resolução do vídeo e à região que será monitorada.

**Segurança:** não publique senhas reais, endereços de acesso com credenciais ou outros dados sensíveis no repositório. Utilize variáveis de ambiente para as credenciais sempre que possível.

## 🚀 Execução

O projeto utiliza Docker para executar a aplicação. Com o Docker e o Docker Compose instalados, e os arquivos de configuração preenchidos, inicie o ambiente com:

```bash
docker compose up --build
```

Para acompanhar os registros da aplicação:

```bash
docker compose logs -f
```

Os comandos pressupõem que o `docker-compose.yml` esteja na raiz do projeto e configure corretamente os serviços e suas dependências.

### Teste de alertas

O módulo de alertas também disponibiliza uma interface de linha de comando para testar o envio de áudio a uma câmera configurada:

```bash
python -m app.alerta --camera Frente
```

Para gerar um arquivo de áudio a partir de um texto:

```bash
python -m app.alerta --gerar "Atenção, pessoa detectada"
```

A execução desses comandos depende das dependências instaladas e da configuração da câmera no ambiente utilizado.

## 📈 Desenvolvimento e próximos passos

O desenvolvimento está concentrado em tornar o monitoramento mais confiável e responsivo.

* [x] Implementação inicial da captura de vídeo por RTSP.
* [x] Integração inicial com YOLO para detecção de pessoas.
* [x] Configuração de zonas de interesse.
* [x] Implementação inicial de alertas sonoros.
* [x] Comunicação direta com câmeras compatíveis.
* [ ] Aprimorar a estabilidade da captura e das reconexões.
* [ ] Medir e reduzir a latência entre a detecção e o alerta.
* [ ] Realizar testes prolongados com múltiplas câmeras.
* [ ] Desenvolver uma interface para configuração e acompanhamento do sistema.
* [ ] Melhorar o monitoramento de erros e a recuperação automática.

## 🤖 Uso de Inteligência Artificial

Este projeto foi desenvolvido com o auxílio de ferramentas de inteligência artificial, utilizadas como apoio durante o desenvolvimento, na investigação de problemas, na elaboração de soluções e na documentação.

A implementação, os testes, as decisões técnicas e a evolução do projeto fazem parte do processo de desenvolvimento e aprendizado do autor.

## 🎯 Objetivo

Desenvolver um sistema de monitoramento inteligente capaz de identificar pessoas em áreas específicas e emitir alertas com baixa latência, mantendo a operação confiável mesmo diante de falhas de conexão.

O projeto também serve como oportunidade de estudo e aplicação prática de visão computacional, processamento de vídeo, comunicação em rede, concorrência e arquitetura de software.

## 📄 Licença

A licença do projeto deverá ser definida de acordo com as condições de distribuição desejadas e as licenças das bibliotecas e dos modelos utilizados.
