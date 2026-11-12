"""Classifica títulos de anúncios nos produtos acompanhados.

Cada anúncio cai em no máximo um produto. Tudo que for acessório, usado,
importado, de outra plataforma ou fora da faixa de preço plausível é descartado.
"""
from __future__ import annotations

import re
import unicodedata

PRODUCTS = {
    "ps5-disco": {"name": "PS5 com leitor de disco", "group": "Console", "min": 2500, "max": 9000},
    "ps5-digital": {"name": "PS5 Edição Digital", "group": "Console", "min": 2000, "max": 8000},
    "ps5-pro": {"name": "PS5 Pro", "group": "Console", "min": 4000, "max": 12000},
    "gta6-padrao": {"name": "GTA VI — Edição Padrão", "group": "Jogo", "min": 150, "max": 900},
    "gta6-ultimate": {"name": "GTA VI — Ultimate Edition", "group": "Jogo", "min": 200, "max": 1200},
    "combo-disco": {"name": "Combo PS5 (disco) + GTA VI", "group": "Combo", "min": 2800, "max": 10000},
    "combo-digital": {"name": "Combo PS5 Digital + GTA VI", "group": "Combo", "min": 2300, "max": 9000},
    "combo-pro": {"name": "Combo PS5 Pro + GTA VI", "group": "Combo", "min": 4300, "max": 13000},
}

# Qualquer um destes em qualquer lugar do título descarta o anúncio.
_EXCLUDE_ANY = [
    "usado", "seminovo", "semi novo", "recondicionado", "vitrine", "open box", "openbox",
    "defeito", "retirada de pecas", "para pecas", "xbox", "nintendo", "switch",
    "playstation 4", "ps4 ", "playstation 3", "ps3", "ps vita", "portal",
    "international version", "middle east", "importado", "versao americana", "us version",
    "japones", "japan", "ksa", "uae ", "versao internacional", "conta primaria", "conta secundaria", "primaria", "secundaria",
    "aluguel", "melhoria", "upgrade", "pacote de dinheiro", "cash card", "gta+",
    "chaveiro", "poster", "camiseta", "caneca", "funko", "action figure", "mapa ",
    "guia ", "adesivo", "skin ", "pelicula", "compativel", "bicicleta", "computador",
    "notebook", "gta v ", "gta 5", "grand theft auto v ", "gta online",
]

# Títulos que começam com isto são acessórios, mesmo citando "PS5".
_EXCLUDE_PREFIX = [
    "controle", "suporte", "capa", "case", "base", "tampa", "leitor de disco", "ssd",
    "hd ", "carregador", "cabo", "bolsa", "mochila", "estojo", "headset", "fone",
    "volante", "cooler", "dock", "hub", "protetor", "interruptor", "analogico", "kit volante",
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().replace("®", "").replace("™", "")
    return re.sub(r"\s+", " ", text).strip() + " "


_GTA6 = re.compile(r"\bgta\s*-?\s*(vi|6)\b|\bgrand theft auto\s*(vi|6)\b")
_PS5 = re.compile(r"\bps\s?5\b|\bplaystation\s?5\b|playstation5")
_STORAGE = re.compile(r"\b(825\s?gb|1\s?tb|2\s?tb)\b")
_PRO = re.compile(r"\bpro\b")
_NOT_DIGITAL_CONSOLE = re.compile(r"jogos? digita(l|is)|codigo digital|midia digital|chave digital|code in box")
_DIGITAL = re.compile(r"\bdigital\b")
_DISC = re.compile(r"leitor de dis(co|k)|com disco|\bdisk\b|\bdisco\b|midia fisica|standard 825")


def classify(title: str, price: float | None, store: str = "") -> str | None:
    """Devolve o id do produto (chave de PRODUCTS) ou None."""
    if not title or price is None or price <= 0:
        return None
    t = normalize(title)
    if any(w in t for w in _EXCLUDE_ANY):
        return None
    if any(t.startswith(p) for p in _EXCLUDE_PREFIX):
        return None

    has_gta = bool(_GTA6.search(t))
    is_ps5 = bool(_PS5.search(t)) or store == "psstore"
    strong_console = (
        "console" in t or bool(_STORAGE.search(t)) or "slim" in t or "bundle" in t
        or "edicao digital" in t or "digital edition" in t
    )
    # Títulos curtos como "PlayStation®5 Pro" (sem GTA no nome) também são o console.
    # ...e títulos que começam pelo nome do console ("PlayStation®5 + God of War").
    short_title = len(t.split()) <= 4 and not has_gta
    starts_console = not has_gta and t.startswith(
        ("playstation5", "playstation 5", "ps5 ", "sony playstation 5", "sony ps5"))
    is_console = (is_ps5 and (strong_console or short_title or starts_console)
                  and not t.startswith("jogo "))

    product: str | None = None
    if is_console:
        t_no_games = _NOT_DIGITAL_CONSOLE.sub(" ", t)
        if _PRO.search(t_no_games):
            kind = "pro"
        elif _DIGITAL.search(t_no_games) and not _DISC.search(t_no_games):
            kind = "digital"
        else:
            kind = "disco"
        product = f"combo-{kind}" if has_gta else f"ps5-{kind}"
    elif has_gta and is_ps5:
        product = "gta6-ultimate" if ("ultimate" in t or "deluxe" in t) else "gta6-padrao"

    if product is None:
        return None
    spec = PRODUCTS[product]
    if not (spec["min"] <= price <= spec["max"]):
        return None
    return product


def parse_brl(text: str | None) -> float | None:
    """'R$ 4.277,07' -> 4277.07"""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?", text.replace("\xa0", " "))
    if not m:
        return None
    inteiro = m.group(1).replace(".", "")
    cents = (m.group(2) or "0").ljust(2, "0")
    return float(f"{inteiro}.{cents}")
