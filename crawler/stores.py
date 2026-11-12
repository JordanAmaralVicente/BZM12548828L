"""Coletores de cada loja.

Cada coletor recebe um contexto do Playwright e devolve uma lista de anúncios
crus ({title, price, url}). Quem decide a qual produto o anúncio pertence é
classify.py. Se a loja mostrar uma página de verificação/captcha, o coletor
lança Blocked: não tentamos contornar proteções anti-robô.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import quote, quote_plus

import requests

from .classify import parse_brl

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

CONSOLE_QUERIES = ["playstation 5 console", "playstation 5 pro"]
GAME_QUERIES = ["gta vi ps5", "grand theft auto vi ps5"]
COMBO_QUERIES = ["playstation 5 gta vi"]
ALL_QUERIES = CONSOLE_QUERIES + GAME_QUERIES + COMBO_QUERIES


class Blocked(Exception):
    """A loja respondeu com bloqueio, captcha ou verificação de conta."""


@dataclass
class Store:
    id: str
    name: str
    home: str


STORES = {
    "amazon": Store("amazon", "Amazon", "https://www.amazon.com.br"),
    "carrefour": Store("carrefour", "Carrefour", "https://www.carrefour.com.br"),
    "kabum": Store("kabum", "Kabum", "https://www.kabum.com.br"),
    "mercadolivre": Store("mercadolivre", "Mercado Livre", "https://www.mercadolivre.com.br"),
    "casasbahia": Store("casasbahia", "Casas Bahia", "https://www.casasbahia.com.br"),
    "psstore": Store("psstore", "PlayStation Store (digital)", "https://store.playstation.com/pt-br"),
}

_BLOCK_MARKERS = re.compile(
    r"account-verification|validateCaptcha|/captcha|access denied|are you a robot|"
    r"sou humano|não sou um robô|nao sou um robo|unusual traffic",
    re.I,
)


async def _open(ctx, url: str, wait_ms: int = 4000, selector: str | None = None):
    page = await ctx.new_page()
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    status = resp.status if resp else 0
    if selector:
        try:
            await page.wait_for_selector(selector, timeout=15000)
        except Exception:
            pass
    await page.wait_for_timeout(wait_ms)
    head = (page.url + " " + (await page.title()) + " " + (await page.content())[:20000])
    if status in (403, 429, 503) or _BLOCK_MARKERS.search(head):
        await page.close()
        raise Blocked(f"HTTP {status} em {page.url[:80]}")
    return page


# --------------------------------------------------------------------- Kabum
def scrape_kabum_sync() -> list[dict]:
    """Kabum expõe a API de catálogo pública usada pelo próprio site."""
    items = []
    for q in ALL_QUERIES:
        r = requests.get(
            "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products",
            params={"query": q, "page_number": 1, "page_size": 100},
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=30,
        )
        if r.status_code in (403, 429):
            raise Blocked(f"HTTP {r.status_code}")
        r.raise_for_status()
        for p in r.json().get("data", []):
            a = p.get("attributes", {})
            if not a.get("available") or a.get("is_openbox"):
                continue
            price = a.get("price_with_discount") or a.get("price")
            offer = a.get("offer") or {}
            if offer.get("price_with_discount"):
                price = min(price, offer["price_with_discount"])
            slug = a.get("product_link") or ""
            url = f"https://www.kabum.com.br/produto/{p['id']}/{slug}".rstrip("/")
            items.append({"title": a.get("title", ""), "price": float(price), "url": url})
    return items


async def scrape_kabum(ctx) -> list[dict]:
    import asyncio
    return await asyncio.to_thread(scrape_kabum_sync)


# -------------------------------------------------------------------- Amazon
_AMAZON_JS = """
() => [...document.querySelectorAll('div[data-component-type="s-search-result"]')].map(el => {
  const h2 = el.querySelector('h2');
  let title = (h2?.getAttribute('aria-label') || h2?.innerText || '').replace(/^Anúncio patrocinado\\s*[–-]\\s*/, '');
  const price = el.querySelector('.a-price:not(.a-text-price) .a-offscreen')?.textContent || null;
  return {asin: el.dataset.asin, title, price};
})
"""


async def scrape_amazon(ctx) -> list[dict]:
    items = []
    for q in ALL_QUERIES:
        page = await _open(ctx, f"https://www.amazon.com.br/s?k={quote_plus(q)}",
                           selector='div[data-component-type="s-search-result"]', wait_ms=1500)
        rows = await page.evaluate(_AMAZON_JS)
        await page.close()
        for r in rows:
            if r["asin"] and r["price"]:
                items.append({"title": r["title"], "price": parse_brl(r["price"]),
                              "url": f"https://www.amazon.com.br/dp/{r['asin']}"})
    return items


# ----------------------------------------------------------------- Carrefour
_CARD_JS = """
() => [...document.querySelectorAll('h2, h3')].map(h => {
  const a = h.closest('a') || h.parentElement?.closest('a') || h.querySelector('a');
  let card = h.parentElement;
  for (let i = 0; i < 5 && card && !/R\\$\\s?\\d/.test(card.innerText); i++) card = card.parentElement;
  if (!card) return null;
  const spans = [...card.querySelectorAll('span, p, div')].filter(e => e.children.length === 0);
  const bold = spans.find(e => /^R\\$\\s?[\\d.]+,\\d{2}$/.test(e.innerText.trim()) && /bold/.test(e.className));
  const any = spans.find(e => /^R\\$\\s?[\\d.]+,\\d{2}$/.test(e.innerText.trim()));
  const link = a?.href || card.querySelector('a')?.href || null;
  return {title: h.innerText.trim(), price: (bold || any)?.innerText || null, url: link};
}).filter(x => x && x.price && x.title)
"""


async def scrape_carrefour(ctx) -> list[dict]:
    items = []
    for q in ["playstation 5", "playstation 5 pro", "gta vi", "grand theft auto vi"]:
        page = await _open(ctx, f"https://www.carrefour.com.br/busca/{quote(q)}", wait_ms=5000)
        rows = await page.evaluate(_CARD_JS)
        await page.close()
        for r in rows:
            items.append({"title": r["title"], "price": parse_brl(r["price"]), "url": r["url"]})
    return items


# ------------------------------------------------------------- Mercado Livre
_ML_JS = """
() => [...document.querySelectorAll('.poly-card, li.ui-search-layout__item')].map(el => {
  const t = el.querySelector('.poly-component__title, .ui-search-item__title, h2, h3');
  const a = el.querySelector('a[href]');
  const cur = el.querySelector('.poly-price__current .andes-money-amount, .andes-money-amount:not(.andes-money-amount--previous)');
  const frac = cur?.querySelector('.andes-money-amount__fraction')?.textContent;
  const cents = cur?.querySelector('.andes-money-amount__cents')?.textContent || '00';
  return {title: t?.innerText?.trim(), price: frac ? `${frac},${cents}` : null, url: a?.href};
}).filter(x => x.title && x.price)
"""


async def scrape_mercadolivre(ctx) -> list[dict]:
    items = []
    for q in ALL_QUERIES:
        slug = q.replace(" ", "-")
        page = await _open(ctx, f"https://lista.mercadolivre.com.br/{slug}_ITEM*CONDITION_2230284",
                           wait_ms=3000)
        rows = await page.evaluate(_ML_JS)
        await page.close()
        for r in rows:
            url = (r["url"] or "").split("#")[0]
            items.append({"title": r["title"], "price": parse_brl(r["price"]), "url": url})
    return items


# --------------------------------------------------------------- Casas Bahia
async def scrape_casasbahia(ctx) -> list[dict]:
    items = []
    for q in ["playstation 5", "gta vi", "grand theft auto vi"]:
        page = await _open(ctx, f"https://www.casasbahia.com.br/{quote(q.replace(' ', '-'))}/b",
                           wait_ms=5000)
        rows = await page.evaluate(_CARD_JS)
        html = await page.content()
        await page.close()
        for r in rows:
            items.append({"title": r["title"], "price": parse_brl(r["price"]), "url": r["url"]})
        items.extend(_jsonld_products(html))
    return items


def _jsonld_products(html: str) -> list[dict]:
    """Extrai Product/Offer de blocos JSON-LD (fallback genérico)."""
    out = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if d.get("@type") == "Product" and d.get("offers"):
                    off = d["offers"]
                    off = off[0] if isinstance(off, list) else off
                    price = off.get("lowPrice") or off.get("price")
                    if price:
                        out.append({"title": d.get("name", ""), "price": float(price),
                                    "url": d.get("url") or off.get("url")})
                stack.extend(v for v in d.values() if isinstance(v, (dict, list)))
    return out


# ----------------------------------------------------------- PlayStation Store
_PSSTORE_JS = """
() => [...document.querySelectorAll('[data-qa^="search#productTile"]')].map(el => {
  const name = el.querySelector('[data-qa$="product-name"]')?.innerText;
  const price = el.querySelector('[data-qa$="display-price"]')?.innerText;
  const a = el.querySelector('a[href]') || el.closest('a');
  return {title: name, price, url: a?.href};
}).filter(x => x.title && x.price && /R\\$/.test(x.price))
"""


async def scrape_psstore(ctx) -> list[dict]:
    page = await _open(ctx, "https://store.playstation.com/pt-br/search/grand%20theft%20auto%20vi",
                       selector='[data-qa^="search#productTile"]', wait_ms=2000)
    rows = await page.evaluate(_PSSTORE_JS)
    await page.close()
    seen, items = set(), []
    for r in rows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        items.append({"title": r["title"], "price": parse_brl(r["price"]), "url": r["url"]})
    return items


SCRAPERS = {
    "amazon": scrape_amazon,
    "carrefour": scrape_carrefour,
    "kabum": scrape_kabum,
    "mercadolivre": scrape_mercadolivre,
    "casasbahia": scrape_casasbahia,
    "psstore": scrape_psstore,
}
