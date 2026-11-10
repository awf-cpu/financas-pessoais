// Dashboard — busca dados da API e desenha gráficos/tabela. PWA registra o SW.
const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
let catChart, monthlyChart;

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.hidden = false;
  clearTimeout(el._t); el._t = setTimeout(() => (el.hidden = true), 3500);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (res.status === 401) { location.href = "/login"; return null; }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function card(label, value, cls = "") {
  return `<div class="card"><div class="label">${label}</div>
          <div class="value ${cls}">${value}</div></div>`;
}

async function loadOverview() {
  const months = document.getElementById("months").value;
  const data = await api(`/api/overview?months=${months}`);
  if (!data) return;
  const t = data.totals;
  document.getElementById("cards").innerHTML =
    card("Saldo em contas", BRL.format(t.balance)) +
    card("Entradas", BRL.format(t.income), "pos") +
    card("Saídas", BRL.format(t.expense), "neg") +
    card("Resultado", BRL.format(t.net), t.net >= 0 ? "pos" : "neg");
  drawCategory(data.by_category);
  drawMonthly(data.monthly);
}

function drawCategory(rows) {
  const ctx = document.getElementById("chart-category");
  catChart?.destroy();
  const palette = ["#38bdf8","#22c55e","#f59e0b","#ef4444","#a78bfa","#f472b6",
                   "#34d399","#fbbf24","#60a5fa","#fb7185","#4ade80","#c084fc"];
  catChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: rows.map(r => r.category),
      datasets: [{ data: rows.map(r => r.total), backgroundColor: palette, borderWidth: 0 }],
    },
    options: {
      plugins: { legend: { position: "bottom", labels: { color: "#94a3b8", boxWidth: 12 } },
        tooltip: { callbacks: { label: c => `${c.label}: ${BRL.format(c.parsed)}` } } },
    },
  });
}

function drawMonthly(rows) {
  const ctx = document.getElementById("chart-monthly");
  monthlyChart?.destroy();
  monthlyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: rows.map(r => r.month),
      datasets: [
        { label: "Entradas", data: rows.map(r => r.income), backgroundColor: "#22c55e" },
        { label: "Saídas", data: rows.map(r => r.expense), backgroundColor: "#ef4444" },
      ],
    },
    options: {
      scales: { x: { ticks: { color: "#94a3b8" }, grid: { display: false } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "#334155" } } },
      plugins: { legend: { labels: { color: "#94a3b8" } },
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${BRL.format(c.parsed.y)}` } } },
    },
  });
}

async function loadTransactions() {
  const search = document.getElementById("search").value.trim();
  const q = search ? `&search=${encodeURIComponent(search)}` : "";
  const rows = await api(`/api/transactions?limit=100${q}`);
  if (!rows) return;
  document.getElementById("tx-body").innerHTML = rows.map(tx => {
    const neg = tx.amount < 0;
    return `<tr>
      <td>${tx.date.split("-").reverse().join("/")}</td>
      <td>${escapeHtml(tx.description)}</td>
      <td><span class="tag">${escapeHtml(tx.category)}</span></td>
      <td class="right"><span class="amount ${neg ? "neg" : "pos"}">${BRL.format(tx.amount)}</span></td>
    </tr>`;
  }).join("") || `<tr><td colspan="4" style="color:var(--muted)">Nenhuma transação ainda. Importe um arquivo ou sincronize.</td></tr>`;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function loadInstitutions() {
  const data = await api("/api/institutions");
  if (!data) return;
  const el = document.getElementById("institutions");
  const list = data.instituicoes || [];
  if (!list.length) {
    el.innerHTML = `<span class="hint">Nenhuma instituição ainda. Importe o relatório CCS para mapear seus bancos.</span>`;
    return;
  }
  el.innerHTML = list.map(i => {
    const dt = i.inicio_relacionamento ? ` · desde ${i.inicio_relacionamento}` : "";
    return `<span class="chip" title="${escapeHtml(i.status)}">${escapeHtml(i.nome)}${dt}</span>`;
  }).join("");
}

document.getElementById("ccs-file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  try {
    const r = await api("/api/registrato", { method: "POST", body: fd });
    if (r) toast(`${r.encontradas} instituição(ões) no CCS, ${r.novas} nova(s) adicionada(s).`);
    await loadInstitutions();
  } catch (err) { toast("Não consegui ler o PDF do CCS. Verifique o arquivo."); }
  e.target.value = "";
});

async function refresh() {
  await Promise.all([loadOverview(), loadTransactions(), loadInstitutions()]);
}

// --- eventos ---
document.getElementById("months").addEventListener("change", loadOverview);
document.getElementById("search").addEventListener("input", debounce(loadTransactions, 300));

document.getElementById("btn-sync").addEventListener("click", async (e) => {
  e.target.disabled = true; e.target.textContent = "Sincronizando...";
  try {
    const r = await api("/api/sync", { method: "POST" });
    if (r) toast(`${r.importadas} nova(s), ${r.duplicadas_ignoradas} já existia(m). Fontes: ${r.fontes.join(", ") || "nenhuma"}`);
    await refresh();
  } catch (err) { toast("Erro ao sincronizar."); }
  finally { e.target.disabled = false; e.target.textContent = "Sincronizar"; }
});

document.getElementById("file").addEventListener("change", async (e) => {
  const files = [...e.target.files];
  let total = 0;
  for (const f of files) {
    const fd = new FormData(); fd.append("file", f);
    try {
      const r = await api("/api/upload", { method: "POST", body: fd });
      if (r) total += r.importadas;
    } catch (err) { toast(`Erro em ${f.name}`); }
  }
  toast(`${total} transação(ões) importada(s).`);
  e.target.value = "";
  await refresh();
});

function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

refresh();
