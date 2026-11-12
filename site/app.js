(() => {
  const STORE_ORDER = ["amazon", "carrefour", "kabum", "mercadolivre", "casasbahia", "psstore"];
  const STATUS_LABEL = { ok: "ok", bloqueado: "bloqueada", erro: "erro", vazio: "sem dados", nunca: "nunca coletada" };
  const brl = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const fmtTs = (ts) => {
    const d = new Date(ts);
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "America/Sao_Paulo" }) +
      " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" });
  };
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") n.className = v; else if (k === "text") n.textContent = v; else n.setAttribute(k, v);
    }
    for (const k of kids) if (k != null) n.append(k);
    return n;
  };

  let DATA = null;
  const charts = [];

  // Linha vertical que acompanha o cursor (crosshair).
  const crosshair = {
    id: "crosshair",
    afterDraw(chart) {
      const a = chart.tooltip?.getActiveElements?.();
      if (!a || !a.length) return;
      const x = a[0].element.x, { top, bottom } = chart.chartArea, ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = css("--axis");
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
      ctx.restore();
    },
  };

  function renderStores() {
    const ul = document.getElementById("stores");
    ul.replaceChildren();
    for (const id of STORE_ORDER) {
      const s = DATA.stores[id];
      if (!s) continue;
      const key = el("span", { class: "key" });
      key.style.background = `var(--s-${id})`;
      const st = s.status === "ok" ? "" : ` · ${STATUS_LABEL[s.status] || s.status}`;
      const li = el("li", { title: s.message || (s.last_ok ? `Última coleta ok: ${fmtTs(s.last_ok)}` : "") },
        key, el("span", { text: s.name }), el("span", { class: "st", text: st }));
      ul.append(li);
    }
  }

  function signalBadge(sig) {
    const label = sig ? sig.signal : "SEM";
    const text = { COMPRA: "COMPRA", AGUARDE: "AGUARDE", NEUTRO: "NEUTRO", COLETANDO: "COLETANDO", SEM: "SEM OFERTAS" }[label];
    return el("span", { class: `badge ${label}` }, el("span", { class: "dot", "aria-hidden": "true" }), text);
  }

  function renderCard(p) {
    const sig = p.signal;
    const card = el("article", { class: "card", "data-group": p.group });
    card.append(el("div", { class: "card-head" },
      el("div", {}, el("div", { class: "group", text: p.group }), el("h2", { text: p.name })),
      signalBadge(sig)));

    if (sig) {
      const store = DATA.stores[sig.store]?.name || sig.store;
      const link = el("a", { href: sig.url, target: "_blank", rel: "noopener", text: store });
      card.append(el("p", { class: "price" }, brl(sig.price), " ", el("small", {}, "na ", link)));
      card.append(el("p", { class: "reason", text: sig.reason }));
      const stat = (label, val) => el("li", {}, el("b", { text: val }), label);
      const pct = (v) => (v > 0 ? "+" : "") + v.toLocaleString("pt-BR") + "%";
      card.append(el("ul", { class: "stats" },
        stat("média 30 dias", brl(sig.avg30)),
        stat("menor já visto", brl(sig.min)),
        stat("vs. média", pct(sig.vs_avg30)),
        stat("histórico", `${sig.days.toLocaleString("pt-BR")} dias`)));
    } else {
      card.append(el("p", { class: "reason", text: "Nenhuma loja tem este produto à venda no momento." }));
    }

    const stores = STORE_ORDER.filter((s) => p.stores[s]?.length);
    if (stores.length) {
      const box = el("div", { class: "chart" });
      const canvas = el("canvas", { role: "img", "aria-label": `Histórico de preço de ${p.name} por loja` });
      box.append(canvas);
      card.append(box);
      requestAnimationFrame(() => drawChart(canvas, p, stores));
    } else {
      card.append(el("div", { class: "empty", text: "Gráfico aparece quando houver ofertas." }));
    }

    if (p.current.length) {
      const tbody = el("tbody");
      for (const c of p.current) {
        tbody.append(el("tr", {},
          el("td", {}, el("a", { href: c.url, target: "_blank", rel: "noopener", text: DATA.stores[c.store]?.name || c.store }),
            el("span", { class: "t", text: c.title })),
          el("td", { class: "num", text: brl(c.price) })));
      }
      card.append(el("details", {}, el("summary", { text: `Preços agora em ${p.current.length} loja(s)` }),
        el("table", {}, el("thead", {}, el("tr", {}, el("th", { text: "Loja / anúncio" }), el("th", { text: "Preço" }))), tbody)));
    }
    return card;
  }

  function drawChart(canvas, p, stores) {
    const labels = [...new Set(stores.flatMap((s) => p.stores[s].map((r) => r[0])))].sort();
    const datasets = stores.map((s) => {
      const m = new Map(p.stores[s].map((r) => [r[0], r[1]]));
      const color = css(`--s-${s}`);
      return {
        label: DATA.stores[s]?.name || s,
        data: labels.map((t) => m.get(t) ?? null),
        borderColor: color, backgroundColor: color,
        borderWidth: 2, pointRadius: labels.length < 3 ? 4 : 0, pointHoverRadius: 5,
        pointHoverBorderColor: css("--surface"), pointHoverBorderWidth: 2,
        spanGaps: true, tension: 0,
      };
    });
    const muted = css("--muted"), grid = css("--grid");
    const chart = new Chart(canvas, {
      type: "line",
      data: { labels: labels.map(fmtTs), datasets },
      plugins: [crosshair],
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { grid: { display: false }, border: { color: css("--axis") },
               ticks: { color: muted, maxRotation: 0, autoSkip: true, font: { size: 11 },
                        maxTicksLimit: canvas.parentElement.clientWidth < 420 ? 4 : 6,
                        callback(v) { return this.getLabelForValue(v).slice(0, 5); } } },
          y: { grid: { color: grid }, border: { display: false },
               ticks: { color: muted, font: { size: 11 }, maxTicksLimit: 5,
                        callback: (v) => "R$ " + Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) } },
        },
        plugins: {
          legend: {
            display: datasets.length > 1, position: "bottom",
            labels: { color: css("--ink-2"), boxWidth: 14, boxHeight: 2, font: { size: 12 } },
          },
          tooltip: {
            backgroundColor: css("--surface"), titleColor: css("--ink-2"), bodyColor: css("--ink"),
            borderColor: css("--axis"), borderWidth: 1, padding: 10, boxWidth: 14, boxHeight: 2,
            itemSort: (a, b) => a.parsed.y - b.parsed.y,
            callbacks: { label: (c) => ` ${brl(c.parsed.y)}  ${c.dataset.label}` },
          },
        },
      },
    });
    charts.push(chart);
  }

  function render() {
    charts.splice(0).forEach((c) => c.destroy());
    const grid = document.getElementById("grid");
    grid.replaceChildren(...DATA.products.map(renderCard));
    applyFilter();
    renderStores();
  }

  let group = "all";
  try { group = localStorage.getItem("grupo") || "all"; } catch {}
  function applyFilter() {
    for (const b of document.querySelectorAll("#filters button")) b.setAttribute("aria-pressed", String(b.dataset.g === group));
    for (const c of document.querySelectorAll(".card")) c.hidden = group !== "all" && c.dataset.group !== group;
  }
  document.getElementById("filters").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    group = b.dataset.g;
    try { localStorage.setItem("grupo", group); } catch {}
    applyFilter();
  });

  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => DATA && render());

  fetch("data.json", { cache: "no-store" })
    .then((r) => r.json())
    .then((d) => {
      DATA = d;
      document.getElementById("updated").textContent = d.last_run
        ? `Última coleta: ${fmtTs(d.last_run)} · atualiza às 9h e 21h`
        : "Ainda sem coletas.";
      render();
    })
    .catch(() => { document.getElementById("updated").textContent = "Não foi possível carregar os dados."; });
})();
