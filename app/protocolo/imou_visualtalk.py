"""Cliente de áudio VisualTalk (câmeras Imou/Dahua).

Abre a sessão de talk na porta 8086 da câmera e envia frames de áudio
AAC/ADTS empacotados em DHAV.
"""

from __future__ import annotations

import re
import socket
import struct
import threading
import time

from .imou_dhav import build_frames
from .imou_wsse import native_nonce, password_digest, utc_created, visualtalk_password_digest

BASE_PATH = (
    "/live/visualtalk.xav?channel={channel}&subtype={subtype}&encrypt={encrypt}"
    "&imagesize=18&audioType=1&trackID={track_id}&method={method}"
)


def default_sdp() -> bytes:
    """Oferta SDP conservadora para abrir o talk."""
    return (
        "v=0\r\n"
        "o=- 0 0 IN IP4 127.0.0.1\r\n"
        "s=Talk\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "t=0 0\r\n"
        "m=video 0 RTP/AVP 96\r\n"
        "a=control:trackID=31\r\n"
        "m=audio 0 RTP/AVP 8 96\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
        "a=rtpmap:96 MPEG4-GENERIC/16000/1\r\n"
        "a=control:trackID=5\r\n"
        "a=sendrecv\r\n"
    ).encode()


class DHHTTPResponse:
    def __init__(self, raw_headers: bytes, body: bytes) -> None:
        self.raw_headers = raw_headers
        self.body = body
        self.text = raw_headers.decode("latin1", errors="replace")
        self.status_line = self.text.split("\r\n", 1)[0]
        partes = self.status_line.split(" ", 2)
        self.code = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 0
        self.headers: dict[str, str] = {}
        for linha in self.text.split("\r\n")[1:]:
            if ": " in linha:
                chave, valor = linha.split(": ", 1)
                self.headers[chave.lower()] = valor

    def body_length(self) -> int:
        return int(self.headers.get("private-length", "0")) or int(self.headers.get("content-length", "0"))


class VisualTalkClient:
    def __init__(self, host: str, port: int, *, username: str, password: str, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.nonce = native_nonce()
        self.created = utc_created()
        self.password_digest = password_digest(self.nonce, self.created, password)
        self.cseq = 0
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)

    def close(self) -> None:
        self.sock.close()

    # ---------------------------------------------------------------- PLAY

    def _path(self, *, channel: int, subtype: int, encrypt: int, track_id: int, method: int,
              talktype: str | None = None) -> str:
        path = BASE_PATH.format(channel=channel, subtype=subtype, encrypt=encrypt,
                                track_id=track_id, method=method)
        return path + f"&talktype={talktype}" if talktype else path

    def _play(self, path: str, *, sdp: bytes = b"", accept_sdp: bool = False) -> DHHTTPResponse:
        cseq = self.cseq
        self.cseq += 1
        resposta = self._play_once(path, cseq, sdp, accept_sdp)
        # A câmera responde 401 com o realm; refaz o digest e repete o mesmo pedido.
        if resposta.code == 401:
            realm = self._realm_do_desafio(resposta)
            if realm:
                self.password_digest = visualtalk_password_digest(
                    self.username, self.password, realm, self.nonce, self.created)
                resposta = self._play_once(path, cseq, sdp, accept_sdp)
        return resposta

    def _play_once(self, path: str, cseq: int, sdp: bytes, accept_sdp: bool) -> DHHTTPResponse:
        wsse = (
            f'UsernameToken Username="{self.username}", PasswordDigest="{self.password_digest}", '
            f'Nonce="{self.nonce}", Created="{self.created}"'
        )
        headers = [
            f"PLAY {path} HTTP/1.1",
            f"Host: {self.host}:{self.port}",
            "Connect-Type: P2P",
            "Connection: close",
            f"Cseq: {cseq}",
            "Speed: 1.000000",
            "User-Agent: Http Stream Client/1.0",
            'Authorization: WSSE profile="UsernameToken"',
            "WSSE: " + wsse,
        ]
        if accept_sdp:
            headers.append("Accpet-Sdp: Private")  # (sic) grafia usada pelo firmware
        if sdp:
            headers.append("Private-Type: application/sdp")
            headers.append(f"Private-Length: {len(sdp)}")
        self.sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode() + sdp)
        return self._ler_resposta()

    @staticmethod
    def _realm_do_desafio(resposta: DHHTTPResponse) -> str | None:
        desafio = resposta.headers.get("www-authenticate", "")
        m = re.search(r'Digest\s+realm="([^"]+)",\s*nonce="([^"]+)"', desafio, re.I)
        return m.group(1) if m else None

    def _ler_resposta(self) -> DHHTTPResponse:
        blob = b""
        while b"\r\n\r\n" not in blob:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise EOFError("socket fechado antes dos headers da resposta")
            blob += chunk
            # descarta frames interleaved ("$") que cheguem antes da resposta
            while blob.startswith(b"$") and len(blob) >= 6:
                total = 6 + struct.unpack_from(">I", blob, 2)[0]
                while len(blob) < total:
                    mais = self.sock.recv(total - len(blob))
                    if not mais:
                        raise EOFError("socket fechado dentro de um frame interleaved")
                    blob += mais
                blob = blob[total:]
            marcador = blob.find(b"HTTP/")
            if marcador > 0:
                blob = blob[marcador:]
        raw_headers, _, corpo = blob.partition(b"\r\n\r\n")
        tamanho = DHHTTPResponse(raw_headers, b"").body_length()
        while len(corpo) < tamanho:
            chunk = self.sock.recv(tamanho - len(corpo))
            if not chunk:
                raise EOFError("socket fechado antes do corpo da resposta")
            corpo += chunk
        return DHHTTPResponse(raw_headers, corpo[:tamanho])

    # ---------------------------------------------------------------- talk

    def start_talk(
        self,
        *,
        channel: int = 1,
        subtype: int = 0,
        encrypt: int = 3,
        track1: int = 0,
        track2: int = 0,
        talk_track: int = 64,
    ) -> list[DHHTTPResponse]:
        """Abre a sessão de talk. Levanta RuntimeError se a câmera recusar.
        track1/track2 = 0 significa "não enviar esse passo"."""
        base = dict(channel=channel, subtype=subtype, encrypt=encrypt)
        passos = [
            (self._path(**base, track_id=31, method=0), dict(sdp=default_sdp(), accept_sdp=True)),
        ]
        if track1:
            passos.append((self._path(**base, track_id=track1, method=0), {}))
        if track2:
            passos.append((self._path(**base, track_id=track2, method=2), {}))
        passos.append((self._path(**base, track_id=talk_track, method=0, talktype="talk"), {}))

        respostas = []
        for path, extra in passos:
            resposta = self._play(path, **extra)
            respostas.append(resposta)
            if resposta.code >= 400:
                raise RuntimeError(f"câmera recusou o áudio: {resposta.status_line}")
        return respostas

    def send_audio(self, audio_adts: bytes, *, sample_rate: int = 16000, frame_ms: int = 64,
                   media_track: int = 5) -> int:
        """Envia AAC/ADTS em tempo real (1 frame a cada frame_ms). Retorna o nº de frames."""
        enviados = 0
        proximo = time.monotonic()
        parar = threading.Event()
        drenar = threading.Thread(target=self._drenar, args=(parar,), daemon=True)
        drenar.start()
        try:
            for frame in build_frames(audio_adts, sample_rate=sample_rate, frame_ms=frame_ms,
                                      track_id=media_track):
                self.sock.sendall(frame)
                enviados += 1
                proximo += frame_ms / 1000.0
                espera = proximo - time.monotonic()
                if espera > 0:
                    time.sleep(espera)
        finally:
            parar.set()
            drenar.join(timeout=0.2)
        return enviados

    def _drenar(self, parar: threading.Event) -> None:
        """Lê (e descarta) o que a câmera devolver, para o buffer não encher."""
        while not parar.is_set():
            try:
                dados = self.sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not dados:
                return