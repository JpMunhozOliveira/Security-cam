"""Autenticação WSSE do VisualTalk (câmeras Imou/Dahua)."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import os
import string

_ALFABETO = string.ascii_lowercase + string.ascii_uppercase + string.digits


def utc_created() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def native_nonce(length: int = 32) -> str:
    """Nonce alfanumérico, no formato do cliente nativo."""
    return "".join(_ALFABETO[b % len(_ALFABETO)] for b in os.urandom(length))


def password_digest(nonce: str, created: str, secret: str) -> str:
    """base64(sha1(nonce + created + secret))."""
    return base64.b64encode(hashlib.sha1(f"{nonce}{created}{secret}".encode()).digest()).decode()


def visualtalk_password_digest(username: str, password: str, realm: str, nonce: str, created: str) -> str:
    """PasswordDigest aceito pelo `visualtalk.xav`.

    O realm do desafio já traz o prefixo "Login to ...", então a chave
    intermediária é MD5("user:<realm>:password") em maiúsculas.
    """
    key = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest().upper()
    return password_digest(nonce, created, key)