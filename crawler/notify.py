"""Alertas por e-mail (Gmail) quando um produto vira COMPRA ou bate novo mínimo."""
from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage

from .classify import PRODUCTS
from .storage import STATE_JSON
from .stores import STORES


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_alerts(signals: dict[str, dict]) -> list[str]:
    """Compara com o estado anterior e devolve as mensagens a enviar. Atualiza o estado."""
    state = json.loads(STATE_JSON.read_text()) if STATE_JSON.exists() else {}
    msgs = []
    for prod, s in signals.items():
        old = state.get(prod, {})
        new_low = (s["signal"] != "COLETANDO" and old.get("min") is not None
                   and s["price"] < old["min"] * 0.99)
        became_buy = s["signal"] == "COMPRA" and old.get("signal") != "COMPRA"
        if became_buy or new_low:
            head = "🟢 COMPRA" if s["signal"] == "COMPRA" else "📉 Novo menor preço"
            msgs.append(
                f"{head}: {PRODUCTS[prod]['name']}\n"
                f"{_brl(s['price'])} na {STORES[s['store']].name}\n"
                f"{s['reason']}\n"
                f"Média 30d: {_brl(s['avg30'])} · Mínimo: {_brl(s['min'])}\n{s['url']}"
            )
        state[prod] = {"signal": s["signal"], "min": min(s["min"], old.get("min", s["min"]))}
    STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    return msgs


def site_url() -> str | None:
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"]
    repo = os.environ.get("GITHUB_REPOSITORY")  # "usuario/repo" dentro do GitHub Actions
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}/"
    return None


def build_email(msgs: list[str], sender: str, to: str) -> EmailMessage:
    first = msgs[0].splitlines()
    subject = (f"{first[0]} — {first[1]}" if len(msgs) == 1
               else f"{len(msgs)} alertas de preço: PS5 / GTA VI")
    body = "\n\n".join(msgs)
    if url := site_url():
        body += f"\n\n—\nGráficos e histórico: {url}"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Preços PS5 <{sender}>"
    msg["To"] = to
    msg.set_content(body)
    return msg


def send_email(msgs: list[str]) -> None:
    """Envia todos os alertas da coleta num único e-mail via SMTP do Gmail.

    Segredos: EMAIL_USER (conta Gmail que envia), EMAIL_APP_PASSWORD (senha de app
    do Google) e EMAIL_TO (destinatário; se vazio, envia para o próprio EMAIL_USER).
    """
    if not msgs:
        return
    user = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_APP_PASSWORD", "").replace(" ", "")
    to = os.environ.get("EMAIL_TO") or user
    if not (user and password):
        print("E-mail não configurado; alertas que seriam enviados:")
        for m in msgs:
            print("  " + m.replace("\n", "\n  "))
        return
    msg = build_email(msgs, user, to)
    try:
        with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"),
                              int(os.environ.get("SMTP_PORT", "465")), timeout=30) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        print(f"E-mail enviado: {msg['Subject']}")
    except Exception as e:
        print(f"Falha ao enviar e-mail: {type(e).__name__}: {e}")
