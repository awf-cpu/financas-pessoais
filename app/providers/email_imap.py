"""Ingestão automática por e-mail via IMAP (ex.: Gmail).

Ideia: bancos e cartões enviam faturas/extratos e avisos por e-mail. Este
módulo conecta na caixa (somente leitura), busca mensagens recentes e extrai
os anexos OFX/CSV/PDF, devolvendo-os para os importadores de arquivos.

100% grátis — usa o e-mail que você já tem. No Gmail, gere uma **senha de app**
(https://myaccount.google.com/apppasswords) e use-a em IMAP_PASSWORD; a senha
normal não funciona com 2FA ativo.

Segurança: a conexão é somente leitura (não marca, move ou apaga nada).
"""
from __future__ import annotations

import email
import imaplib
from dataclasses import dataclass
from datetime import date, timedelta
from email.message import Message

from ..config import get_settings

# Extensões de anexo que sabemos importar.
_SUPPORTED_EXT = (".ofx", ".qfx", ".csv", ".pdf")


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    sender: str
    subject: str


def fetch_statement_attachments(max_messages: int = 200) -> list[EmailAttachment]:
    """Busca anexos de extrato/fatura em e-mails recentes. Lista vazia se desligado."""
    s = get_settings()
    if not s.imap_enabled:
        return []

    since = (date.today() - timedelta(days=s.imap_search_days)).strftime("%d-%b-%Y")
    attachments: list[EmailAttachment] = []

    client = imaplib.IMAP4_SSL(s.imap_host, s.imap_port)
    try:
        client.login(s.imap_user, s.imap_password)
        client.select(s.imap_folder, readonly=True)  # readonly = não altera nada
        status, data = client.search(None, f'(SINCE "{since}")')
        if status != "OK":
            return []
        ids = data[0].split()[-max_messages:]
        for msg_id in ids:
            status, msg_data = client.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data:
                continue
            raw = _first_bytes(msg_data)
            if raw is None:
                continue
            msg = email.message_from_bytes(raw)
            sender = str(msg.get("From", ""))
            subject = _decode_header(msg.get("Subject", ""))
            for att in _extract_attachments(msg):
                att.sender = sender
                att.subject = subject
                attachments.append(att)
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return attachments


def _first_bytes(msg_data: list) -> bytes | None:
    for part in msg_data:
        if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], (bytes, bytearray)):
            return bytes(part[1])
    return None


def _decode_header(value: str) -> str:
    from email.header import decode_header

    parts = []
    for text, enc in decode_header(value or ""):
        if isinstance(text, bytes):
            parts.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts)


def _extract_attachments(msg: Message) -> list[EmailAttachment]:
    out: list[EmailAttachment] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        filename = _decode_header(filename)
        if not filename.lower().endswith(_SUPPORTED_EXT):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        out.append(
            EmailAttachment(filename=filename, content=payload, sender="", subject="")
        )
    return out
