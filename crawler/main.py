"""Roda uma coleta completa: lojas -> CSV -> site/data.json -> alertas.

Uso:
  python -m crawler.main            # coleta + gera site + alertas
  python -m crawler.main --build    # só regera site/data.json a partir do CSV
  python -m crawler.main --stores kabum,amazon
"""
from __future__ import annotations

import argparse
import asyncio
import json
import traceback
from datetime import datetime, timezone, timedelta

from .classify import PRODUCTS, classify
from .notify import build_alerts, send_email
from .signals import best_series, compute
from .storage import ROOT, append_prices, append_runs, load_prices, load_runs
from .stores import SCRAPERS, STORES, UA, Blocked

BRT = timezone(timedelta(hours=-3))
SITE_DATA = ROOT / "site" / "data.json"


async def collect(store_ids: list[str]) -> tuple[list[dict], list[dict]]:
    from playwright.async_api import async_playwright

    ts = datetime.now(BRT).replace(microsecond=0).isoformat()
    prices, runs = [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for sid in store_ids:
            ctx = await browser.new_context(user_agent=UA, locale="pt-BR",
                                            viewport={"width": 1366, "height": 900})
            run = {"ts": ts, "store": sid, "status": "ok", "raw_items": 0, "matched": 0, "message": ""}
            try:
                items = await asyncio.wait_for(SCRAPERS[sid](ctx), timeout=240)
                run["raw_items"] = len(items)
                best: dict[str, dict] = {}
                for it in items:
                    prod = classify(it["title"], it["price"], sid)
                    if prod and (prod not in best or it["price"] < best[prod]["price"]):
                        best[prod] = {"ts": ts, "store": sid, "product": prod, **it}
                prices.extend(best.values())
                run["matched"] = len(best)
                if not items:
                    run.update(status="vazio", message="Nenhum anúncio encontrado (layout mudou?)")
            except Blocked as e:
                run.update(status="bloqueado", message=str(e))
            except Exception as e:
                run.update(status="erro", message=f"{type(e).__name__}: {str(e)[:200]}")
                traceback.print_exc()
            finally:
                await ctx.close()
            print(f"[{sid}] {run['status']} — {run['raw_items']} anúncios, {run['matched']} produtos "
                  f"{run['message']}")
            for p in sorted((p for p in prices if p["store"] == sid), key=lambda p: p["product"]):
                print(f"    {p['product']:<14} R$ {p['price']:>9.2f}  {p['title'][:70]}")
            runs.append(run)
        await browser.close()
    return prices, runs


def best_deals(current: dict[str, list[dict]]) -> list[dict]:
    """Para cada modelo de PS5: o jeito mais barato de levar console + GTA VI agora.

    Compara comprar separado (console na loja X + jogo na loja Y) com o combo.
    `current` é {produto: [ofertas da última coleta, já ordenadas por preço]}.
    """
    def cheapest(pid: str) -> dict | None:
        offers = current.get(pid) or []
        return {**offers[0], "product": pid, "name": PRODUCTS[pid]["name"]} if offers else None

    game = cheapest("gta6-padrao")
    deals = []
    for kind in ("digital", "disco", "pro"):
        console, combo = cheapest(f"ps5-{kind}"), cheapest(f"combo-{kind}")
        options = []
        if console and game:
            options.append({"type": "separado", "total": round(console["price"] + game["price"], 2),
                            "items": [console, game]})
        if combo:
            options.append({"type": "combo", "total": combo["price"], "items": [combo]})
        if not options:
            continue
        options.sort(key=lambda o: o["total"])
        deals.append({
            "kind": kind, "name": PRODUCTS[f"ps5-{kind}"]["name"], "best": options[0],
            "alt": options[1] if len(options) > 1 else None,
        })
    deals.sort(key=lambda d: d["best"]["total"])
    return deals


def build_site() -> dict[str, dict]:
    rows = load_prices()
    runs = load_runs()
    series = best_series(rows)
    signals = {p: compute(s) for p, s in series.items()}

    products = []
    for pid, spec in PRODUCTS.items():
        by_store: dict[str, list] = {}
        for r in rows:
            if r["product"] == pid:
                by_store.setdefault(r["store"], []).append([r["ts"], r["price"]])
        latest_ts = max((r["ts"] for r in rows), default=None)
        current = sorted(
            ({"store": r["store"], "price": r["price"], "title": r["title"], "url": r["url"]}
             for r in rows if r["product"] == pid and r["ts"] == latest_ts),
            key=lambda x: x["price"],
        )
        products.append({
            "id": pid, "name": spec["name"], "group": spec["group"],
            "signal": signals.get(pid),
            "best": [[p["ts"], p["price"], p["store"]] for p in series.get(pid, [])],
            "stores": by_store, "current": current,
        })

    deals = best_deals({p["id"]: p["current"] for p in products})

    store_status = {}
    for sid, st in STORES.items():
        mine = [r for r in runs if r["store"] == sid]
        last = mine[-1] if mine else None
        last_ok = next((r["ts"] for r in reversed(mine) if r["status"] == "ok" and int(r["matched"] or 0) > 0), None)
        store_status[sid] = {"name": st.name, "home": st.home,
                             "status": last["status"] if last else "nunca",
                             "message": last["message"] if last else "", "last_ok": last_ok}

    SITE_DATA.parent.mkdir(exist_ok=True)
    SITE_DATA.write_text(json.dumps({
        "generated": datetime.now(BRT).replace(microsecond=0).isoformat(),
        "last_run": runs[-1]["ts"] if runs else None,
        "products": products, "stores": store_status, "deals": deals,
    }, ensure_ascii=False, separators=(",", ":")))
    return signals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="só regera o site a partir do CSV")
    ap.add_argument("--stores", default=",".join(SCRAPERS), help="lojas separadas por vírgula")
    ap.add_argument("--no-alerts", action="store_true")
    args = ap.parse_args()

    if not args.build:
        prices, runs = asyncio.run(collect([s.strip() for s in args.stores.split(",") if s.strip()]))
        append_prices(prices)
        append_runs(runs)
    signals = build_site()
    for pid, s in signals.items():
        print(f"{s['signal']:<10} {PRODUCTS[pid]['name']:<30} R$ {s['price']:>9.2f} ({s['store']}) — {s['reason']}")
    if not args.build and not args.no_alerts:
        send_email(build_alerts(signals))


if __name__ == "__main__":
    main()
