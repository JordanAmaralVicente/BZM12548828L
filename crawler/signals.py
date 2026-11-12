"""Sinal COMPRA / NEUTRO / AGUARDE a partir do histórico do menor preço.

Para cada produto, a série usada é o menor preço entre todas as lojas em cada
coleta. Regras (na ordem):

  COMPRA   preço atual é o menor já registrado, ou está até 3% acima do mínimo
           histórico, ou está 8%+ abaixo da média dos últimos 30 dias.
  AGUARDE  preço 3%+ acima da média de 30 dias, ou o preço vem caindo nos
           últimos dias (tende a cair mais), ou a Black Friday está perto.
  NEUTRO   o resto: preço dentro do normal.

Com menos de 3 dias de coleta o sinal fica como COLETANDO.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import mean

MIN_DAYS = 3
NEAR_LOW = 1.03
BELOW_AVG = 0.92
ABOVE_AVG = 1.03
FALLING = 0.97          # média dos últimos 3 dias 3% abaixo dos 4 dias anteriores
BLACK_FRIDAY_WINDOW = 15  # dias antes da Black Friday em que preferimos esperar


def black_friday(year: int) -> date:
    nov1 = date(year, 11, 1)
    first_thu = nov1 + timedelta(days=(3 - nov1.weekday()) % 7)
    return first_thu + timedelta(weeks=3, days=1)


def best_series(rows: list[dict]) -> dict[str, list[dict]]:
    """{product: [{ts, price, store, url, title}, ...]} — menor preço por coleta."""
    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        k = (r["product"], r["ts"])
        if k not in best or r["price"] < best[k]["price"]:
            best[k] = r
    out: dict[str, list[dict]] = {}
    for (prod, _), r in best.items():
        out.setdefault(prod, []).append(
            {"ts": r["ts"], "price": r["price"], "store": r["store"], "url": r["url"], "title": r["title"]}
        )
    for s in out.values():
        s.sort(key=lambda x: x["ts"])
    return out


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def compute(series: list[dict], today: date | None = None) -> dict:
    cur = series[-1]
    now = _ts(cur["ts"])
    today = today or now.date()
    prices = [p["price"] for p in series]
    prev = prices[:-1]
    last30 = [p["price"] for p in series if _ts(p["ts"]) >= now - timedelta(days=30)]
    avg30 = mean(last30)
    hist_min = min(prices)
    days = (now - _ts(series[0]["ts"])).total_seconds() / 86400

    info = {
        "price": cur["price"], "store": cur["store"], "url": cur["url"], "title": cur["title"],
        "ts": cur["ts"], "min": hist_min, "max": max(prices), "avg30": round(avg30, 2),
        "vs_avg30": round((cur["price"] / avg30 - 1) * 100, 1),
        "vs_min": round((cur["price"] / hist_min - 1) * 100, 1),
        "days": round(days, 1),
    }

    bf = black_friday(today.year)
    to_bf = (bf - today).days

    if days < MIN_DAYS:
        quando = "menos de 1 dia" if days < 1 else f"{int(days)} dia(s)"
        info.update(signal="COLETANDO",
                    reason=f"Coletando há {quando}; o sinal começa após {MIN_DAYS} dias de histórico.")
        return info

    def window(lo: int, hi: int) -> list[float]:
        return [p["price"] for p in series if now - timedelta(days=hi) <= _ts(p["ts"]) < now - timedelta(days=lo)]

    recent, before = window(0, 3) + [cur["price"]], window(3, 7)
    falling = bool(before) and mean(recent) <= mean(before) * FALLING

    if prev and cur["price"] < min(prev):
        signal, reason = "COMPRA", "Menor preço já registrado."
    elif cur["price"] <= hist_min * NEAR_LOW:
        signal, reason = "COMPRA", f"A {info['vs_min']}% do menor preço já visto."
    elif cur["price"] <= avg30 * BELOW_AVG:
        signal, reason = "COMPRA", f"{-info['vs_avg30']}% abaixo da média de 30 dias."
    elif cur["price"] >= avg30 * ABOVE_AVG:
        signal, reason = "AGUARDE", f"{info['vs_avg30']}% acima da média de 30 dias."
    elif falling:
        signal, reason = "AGUARDE", "Preço em queda nos últimos dias; pode cair mais."
    elif 0 <= to_bf <= BLACK_FRIDAY_WINDOW:
        signal, reason = "AGUARDE", f"Black Friday em {to_bf} dia(s) ({bf:%d/%m}); costuma ter desconto."
    else:
        signal, reason = "NEUTRO", "Preço dentro do normal. Compre se precisar agora."
    info.update(signal=signal, reason=reason)
    return info
