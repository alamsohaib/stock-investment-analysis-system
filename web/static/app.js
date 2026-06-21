"use strict";

/* ------------------------------------------------------------------ */
/* helpers                                                            */
/* ------------------------------------------------------------------ */
const $ = (sel) => document.querySelector(sel);
const api = (path) => fetch(path).then((r) => r.json());

function fmt(n, dp = 2) {
  if (n === null || n === undefined || n === "" || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-PK", { minimumFractionDigits: dp, maximumFractionDigits: dp });
}
function fmtInt(n) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-PK");
}
function scoreColor(s) {
  if (s == null) return "#9aa6b8";
  if (s >= 70) return "#138a4e";
  if (s >= 55) return "#1f6feb";
  if (s >= 45) return "#b5740c";
  return "#c4322f";
}
function recClass(rec) {
  return "rec rec-" + (rec || "").toLowerCase().replace(/\s+/g, "-");
}
function badge(kind) {
  const k = (kind || "calculated").toLowerCase();
  const label = { actual: "Actual", calculated: "Calculated", assumption: "Assumption",
                  opinion: "Opinion", external: "External" }[k] || k;
  return `<span class="badge badge-${k}">${label}</span>`;
}
function signalColor(s) {
  return { green: "var(--green)", amber: "var(--amber)", red: "var(--red)",
           Bullish: "var(--green)", Neutral: "var(--amber)", Bearish: "var(--red)" }[s] || "var(--muted)";
}
// radial score gauge (SVG, no libs)
function gauge(score, size = 96) {
  const v = Math.max(0, Math.min(100, score || 0));
  const r = (size - 14) / 2, c = 2 * Math.PI * r, off = c * (1 - v / 100);
  const col = scoreColor(score);
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="gauge">
    <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="#e7ebf2" stroke-width="9"/>
    <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${col}" stroke-width="9"
      stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}"
      transform="rotate(-90 ${size/2} ${size/2})"/>
    <text x="50%" y="50%" text-anchor="middle" dy="0.05em" class="gauge-num" fill="${col}">${fmt(score,0)}</text>
    <text x="50%" y="50%" text-anchor="middle" dy="1.5em" class="gauge-sub">/100</text>
  </svg>`;
}
function fmtBig(n) {
  if (n == null || isNaN(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e12) return (n/1e12).toFixed(2) + " T";
  if (a >= 1e9)  return (n/1e9).toFixed(2) + " bn";
  if (a >= 1e6)  return (n/1e6).toFixed(2) + " mn";
  if (a >= 1e3)  return (n/1e3).toFixed(1) + " k";
  return fmt(n, 0);
}
function scoreBar(s, w = 60) {
  const v = Math.max(0, Math.min(100, s || 0));
  return `<span class="score-bar" style="width:${w}px"><i style="width:${v}%;background:${scoreColor(s)}"></i></span>`;
}
function mosCell(m) {
  if (m == null) return `<span class="muted">—</span>`;
  const cls = m >= 0 ? "pos" : "neg";
  const sign = m >= 0 ? "+" : "";
  return `<span class="${cls}">${sign}${fmt(m, 1)}%</span>`;
}

/* ------------------------------------------------------------------ */
/* state                                                             */
/* ------------------------------------------------------------------ */
let SCAN = null;           // last scan result
let CURRENT_TAB = "top";
let pollTimer = null;

/* ------------------------------------------------------------------ */
/* status + scan                                                     */
/* ------------------------------------------------------------------ */
async function loadStatus() {
  try {
    const s = await api("/api/status");
    const meta = $("#statusMeta");
    meta.textContent = `Server time: ${s.server_time_utc} · Source: ${s.data_source}`;
    if (s.scan && s.scan.has_result) {
      // a scan already finished server-side — pull it
      fetchScan(false);
    }
  } catch (e) {
    $("#statusText").innerHTML = `<span class="neg">Could not reach the server. Is it running?</span>`;
  }
}

function startScan() {
  $("#scanBtn").disabled = true;
  $("#scanBtn").textContent = "Scanning…";
  $("#progressBox").classList.remove("hidden");
  $("#statusText").innerHTML = "Scanning the Pakistan Stock Exchange…";
  fetch("/api/scan?force=1&top=20").then(() => poll());
}

function poll() {
  clearTimeout(pollTimer);
  api("/api/scan/status").then((st) => {
    $("#progressLog").textContent = (st.progress || []).slice(-8).join("\n");
    if (st.error) {
      $("#progressTitle").innerHTML = `<span class="neg">Scan error: ${st.error}</span>`;
    }
    if (st.has_result && !st.running) {
      SCAN = st.result;
      onScanDone();
    } else {
      pollTimer = setTimeout(poll, 1500);
    }
  }).catch(() => { pollTimer = setTimeout(poll, 2000); });
}

function fetchScan(force) {
  api("/api/scan" + (force ? "?force=1" : "")).then((d) => {
    if (d.ready && d.result) { SCAN = d.result; onScanDone(); }
    else { poll(); }
  });
}

function onScanDone() {
  $("#scanBtn").disabled = false;
  $("#scanBtn").textContent = "Refresh Analysis";
  $("#progressBox").classList.add("hidden");
  $("#resultsSection").classList.remove("hidden");
  const m = SCAN.meta;
  $("#statusText").innerHTML =
    `Analysed <strong>${m.deep_analysed}</strong> of ${m.universe_total} tradeable stocks.`;
  $("#statusMeta").textContent = `Generated ${m.report_generated}`;
  renderTable();
}

/* ------------------------------------------------------------------ */
/* opportunities table                                               */
/* ------------------------------------------------------------------ */
function renderTable() {
  if (!SCAN) return;
  const rows = CURRENT_TAB === "value" ? SCAN.undervalued : SCAN.opportunities;
  const body = $("#oppBody");
  body.innerHTML = "";
  if (!rows || !rows.length) {
    body.innerHTML = `<tr><td colspan="9" class="muted" style="padding:24px">No stocks matched this view.</td></tr>`;
  }
  rows.forEach((o, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><span class="sym-cell">${o.symbol}</span>${o.speculative ? ' <span class="spec-tag" title="Flagged speculative — thin/penny/micro-cap. Higher risk.">⚠</span>' : ''}</td>
      <td class="company-cell hide-sm">${o.name || ""}</td>
      <td class="num">${fmt(o.price)}</td>
      <td class="num">${fmt(o.fair_value)}</td>
      <td class="num">${mosCell(o.margin_of_safety_pct)}</td>
      <td class="num"><span class="score-pill">${scoreBar(o.investment_score)}<span class="score-num" style="color:${scoreColor(o.investment_score)}">${fmt(o.investment_score, 0)}</span></span></td>
      <td><span class="${recClass(o.recommendation)}">${o.recommendation}</span></td>
      <td class="num hide-sm muted">${o.data_coverage_pct}%</td>`;
    tr.addEventListener("click", () => openStock(o.symbol));
    body.appendChild(tr);
  });
  $("#tableFootnote").innerHTML =
    `Weights — Fundamental 40% · Technical 25% · Fair Value 20% · Broker 10% · News 5%. ` +
    `“Data” = how much of the score rests on available data. Click any row for the full breakdown.`;
}

/* ------------------------------------------------------------------ */
/* search                                                            */
/* ------------------------------------------------------------------ */
let searchTimer = null;
function onSearch(e) {
  const q = e.target.value.trim();
  clearTimeout(searchTimer);
  const box = $("#searchResults");
  if (q.length < 1) { box.classList.add("hidden"); return; }
  searchTimer = setTimeout(() => {
    api("/api/search?q=" + encodeURIComponent(q)).then((d) => {
      const r = d.results || [];
      if (!r.length) { box.classList.add("hidden"); return; }
      box.innerHTML = r.map((s) =>
        `<div class="sr-item" data-sym="${s.symbol}"><span class="sr-sym">${s.symbol}</span><span class="sr-name">${s.name || ""}</span></div>`).join("");
      box.classList.remove("hidden");
      box.querySelectorAll(".sr-item").forEach((it) =>
        it.addEventListener("click", () => {
          box.classList.add("hidden"); $("#searchInput").value = "";
          openStock(it.dataset.sym);
        }));
    });
  }, 220);
}

/* ------------------------------------------------------------------ */
/* drawer (deep dive)                                                */
/* ------------------------------------------------------------------ */
function openStock(symbol) {
  $("#drawerOverlay").classList.remove("hidden");
  $("#drawer").classList.remove("hidden");
  $("#drawerContent").innerHTML =
    `<div class="d-head"><div class="spinner" style="margin:40px auto"></div>
     <p class="muted" style="text-align:center">Building institutional research report for ${symbol}…<br>
     <span class="small">(fetching PSX + StockAnalysis data)</span></p></div>`;
  Promise.all([api("/api/deepdive/" + symbol), api("/api/history/" + symbol)])
    .then(([rep, hist]) => renderDeepDive(rep, hist))
    .catch((e) => {
      $("#drawerContent").innerHTML = `<div class="d-head"><p class="neg">Could not analyse ${symbol}: ${e}</p></div>`;
    });
}
function closeDrawer() {
  $("#drawer").classList.add("hidden");
  $("#drawerOverlay").classList.add("hidden");
}

function metricRow(c) {
  const v = (c.value === null || c.value === undefined) ? "—" : c.value;
  return `<div class="metric">
    <div class="m-left"><span class="m-label">${c.label}</span>
      ${c.explain ? `<span class="m-explain">${c.explain}</span>` : ""}</div>
    <div class="m-right"><span class="m-value">${v}</span>${badge(c.kind)}
      ${c.subscore != null ? `<span class="muted small">${fmt(c.subscore,0)}/100</span>` : ""}</div>
  </div>`;
}

function kpi(label, val, sub) {
  return `<div class="kpi"><div class="kpi-label">${label}</div>
    <div class="kpi-val">${val}</div>${sub ? `<div class="kpi-sub">${sub}</div>` : ""}</div>`;
}

function renderDeepDive(r, hist) {
  const v = r.verdict, mk = r.market, o = r.overview, t = r.technical,
        val = r.valuation, ac = r.analyst_consensus, f = r.fundamentals;
  const chg = r.change_pct;
  const chgHtml = chg == null ? "" :
    `<span class="${chg>=0?'pos':'neg'}">${chg>=0?'▲':'▼'} ${fmt(Math.abs(chg),2)}%</span>`;
  const ti = t.indicators || {};

  // pillar breakdown (single-stock weights)
  const plabels = {fundamentals:"Fundamentals", valuation:"Valuation", technicals:"Technicals",
    broker_activity:"Broker / Smart Money", institutional_consensus:"Analyst Consensus", news_sentiment:"News"};
  const bdRows = Object.keys(v.breakdown).map((k) => `
    <div class="bd-row"><span class="bd-label">${plabels[k]}</span>
      ${scoreBar(v.breakdown[k], 0)}
      <span class="bd-val" style="color:${scoreColor(v.breakdown[k])}">${fmt(v.breakdown[k],0)}</span>
      <span class="bd-w">${Math.round(v.weights[k]*100)}%</span></div>`).join("");

  // peers table
  const peers = (val.peers||[]);
  const peerRows = peers.length ? peers.map((p)=>`<tr>
      <td class="sym-cell">${p.symbol}</td><td class="num">${fmt(p.price)}</td>
      <td class="num">${p.pe!=null?fmt(p.pe,1):"—"}</td>
      <td class="num">${p.market_cap_bn!=null?fmt(p.market_cap_bn,1):"—"}</td></tr>`).join("")
    : `<tr><td colspan="4" class="muted">No sector peers found.</td></tr>`;

  // valuation scenarios
  const valHtml = val.base ? `
    <div class="setup-grid">
      <div class="setup-cell"><div class="sc-label">Conservative</div><div class="sc-value">${fmt(val.conservative)}</div></div>
      <div class="setup-cell entry"><div class="sc-label">Base (fair)</div><div class="sc-value">${fmt(val.base)}</div></div>
      <div class="setup-cell"><div class="sc-label">Bull</div><div class="sc-value">${fmt(val.bull)}</div></div>
      <div class="setup-cell"><div class="sc-label">Margin of Safety</div><div class="sc-value">${mosCell(val.margin_of_safety_pct)}</div></div>
    </div>` : `<p class="muted">Scenario fair value could not be computed (EPS unavailable).</p>`;
  const valMethods = val.methods.map((mm)=>`<div class="metric">
      <div class="m-left"><span class="m-label">${mm.method}</span><span class="m-explain">${mm.note||""}</span></div>
      <div class="m-right"><span class="m-value">${mm.fair_value!=null?fmt(mm.fair_value):"n/a"}</span>${badge(mm.kind)}</div></div>`).join("");
  const hc = val.historical || {};
  const histHtml = `<div class="setup-grid" style="margin-top:8px">
      ${miniCell("1-yr avg price", fmt(hc.avg_1y))}
      ${miniCell("3-yr avg price", fmt(hc.avg_3y))}
      ${miniCell("5-yr avg price", fmt(hc.avg_5y))}
    </div><p class="muted small" style="margin-top:6px">${hc.note||""}</p>`;

  // plan
  const pl = r.plan, ret = r.returns;
  let planHtml = `<p class="muted">No trade plan available.</p>`;
  if (pl.available) {
    planHtml = `
      <div class="setup-grid">
        <div class="setup-cell entry"><div class="sc-label">Ideal Buy</div><div class="sc-value">${fmt(pl.entry.ideal_buy)}</div></div>
        <div class="setup-cell entry"><div class="sc-label">Accumulation Zone</div><div class="sc-value">${pl.accumulation_zone?fmt(pl.accumulation_zone[0])+"–"+fmt(pl.accumulation_zone[1]):fmt(pl.entry.max_buy)}</div></div>
        <div class="setup-cell sl"><div class="sc-label">Stop Loss</div><div class="sc-value">${fmt(pl.stop_loss.price)} <span class="small">(${fmt(pl.stop_loss.pct,1)}%)</span></div></div>
        <div class="setup-cell"><div class="sc-label">Risk / Reward</div><div class="sc-value">${pl.expected.risk_reward ?? "—"} : 1</div></div>
      </div>
      <div class="targets">
        <div class="target"><div class="t-k">Target 1</div><div class="t-v">${fmt(pl.targets.t1)}</div></div>
        <div class="target"><div class="t-k">Target 2</div><div class="t-v">${fmt(pl.targets.t2)}</div></div>
        <div class="target"><div class="t-k">Target 3</div><div class="t-v">${fmt(pl.targets.t3)}</div></div>
      </div>
      ${ret.available?`<div class="setup-grid" style="margin-top:10px">
        ${miniCell("6-month est. return", (ret.est_6m_pct>=0?"+":"")+fmt(ret.est_6m_pct,1)+"%")}
        ${miniCell("12-month est. return", (ret.est_12m_pct>=0?"+":"")+fmt(ret.est_12m_pct,1)+"%")}
        ${miniCell("Volatility (annual)", ret.volatility_pct!=null?fmt(ret.volatility_pct,1)+"%":"—")}
      </div><p class="muted small" style="margin-top:6px">${badge("opinion")} ${ret.note}</p>`:""}
      <p class="muted small" style="margin-top:8px">Horizon: ${pl.horizon}</p>
      <div class="note warn">${pl.note}</div>`;
  }

  // analyst consensus card
  const acHtml = ac.available ? `
      <div class="consensus">
        <div class="consensus-rating ${recClass(ac.rating)}">${ac.rating}</div>
        <div class="consensus-detail">
          <div><span class="muted">12-month target:</span> <strong>Rs ${fmt(ac.target_price)}</strong>
            ${ac.target_upside_pct!=null?`<span class="${ac.target_upside_pct>=0?'pos':'neg'}">(${ac.target_upside_pct>=0?'+':''}${fmt(ac.target_upside_pct,1)}%)</span>`:""}</div>
          <div class="muted small">${ac.source}</div>
        </div>
        <div class="consensus-gauge">${gauge(ac.score, 80)}</div>
      </div>
      <div class="note">${badge("external")} ${ac.note}</div>`
    : `<div class="note warn">${ac.note}</div>`;

  // key people
  const people = (o.key_people||[]).map((p)=>`<span class="person"><strong>${p.name}</strong> · ${p.role}</span>`).join("");

  // signal pill
  const sigCol = signalColor(t.signal);

  $("#drawerContent").innerHTML = `
    <div class="d-head">
      <div class="d-symline">
        <span class="d-sym">${r.symbol}</span>
        <span class="d-name">${r.name}</span>
        ${r.external_available?`<span class="src-pill">+ StockAnalysis</span>`:`<span class="src-pill src-pill--off">PSX only</span>`}
      </div>
      <div class="d-symline" style="margin-top:6px">
        <span class="d-price">Rs ${fmt(r.price)}</span> ${chgHtml}
      </div>
      <div class="d-sub">${o.sector||"—"}${o.industry?" · "+o.industry:""} · Overall confidence: ${r.confidence_overall} · Data coverage ${v.data_coverage_pct}%</div>
    </div>

    <!-- ⭐ VERDICT -->
    <div class="card verdict-card">
      <div class="verdict-top">
        <div class="verdict-gauge">${gauge(v.overall_score, 116)}<div class="muted small" style="text-align:center">Investment Score</div></div>
        <div class="verdict-main">
          <div class="muted small">⭐ FINAL VERDICT</div>
          <span class="${recClass(v.recommendation)}" style="font-size:20px;padding:9px 20px;margin:6px 0;display:inline-block">${v.recommendation}</span>
          <p class="d-sub" style="max-width:430px">${v.action_hint} ${badge("opinion")}</p>
        </div>
      </div>
      <div style="margin-top:8px">${bdRows}</div>
      <p class="muted small" style="margin-top:6px">Weights — Fundamentals 35% · Valuation 25% · Technicals 15% · Broker 10% · Analyst 10% · News 5%.</p>
      ${v.speculative ? `<div class="note warn"><strong>⚠ Flagged SPECULATIVE.</strong>
        <ul class="unavailable-list">${(v.risk_flags||[]).map(x=>`<li>${x}</li>`).join("")}</ul></div>`:""}
    </div>

    <!-- 📊 MARKET SNAPSHOT -->
    <div class="card">
      <h3>📊 Market Snapshot</h3>
      <div class="kpi-grid">
        ${kpi("Price", "Rs "+fmt(mk.current_price), chgHtml)}
        ${kpi("Previous Close", "Rs "+fmt(mk.previous_close))}
        ${kpi("Day Range", fmt(mk.day_low)+" – "+fmt(mk.day_high))}
        ${kpi("52-Week Range", fmt(mk.week52_low)+" – "+fmt(mk.week52_high))}
        ${kpi("Avg Volume (30d)", fmtBig(mk.avg_daily_volume_30d))}
        ${kpi("Today Volume", fmtBig(mk.today_volume))}
        ${kpi("Market Cap", "Rs "+fmtBig(mk.market_cap))}
        ${kpi("Dividend Yield", mk.dividend_yield_pct!=null?fmt(mk.dividend_yield_pct,2)+"%":"—", mk.dividend_yield_pct!=null?badge("external"):"")}
        ${kpi("Beta", mk.beta!=null?fmt(mk.beta,2):"—", mk.beta!=null?badge("external"):"")}
        ${kpi("Enterprise Value", "—", "needs net debt")}
      </div>
    </div>

    <!-- 🏢 COMPANY PROFILE -->
    <div class="card">
      <h3>🏢 Company Profile</h3>
      <div class="kpi-grid">
        ${kpi("Sector", o.sector||"—")}
        ${kpi("Industry", (o.industry||"—")+(o.industry?" ":""), o.industry?badge("external"):"")}
        ${kpi("Shares Outstanding", fmtBig(o.shares_outstanding))}
        ${kpi("Free Float", o.free_float_pct!=null?fmt(o.free_float_pct,1)+"%":"—")}
        ${kpi("Founded", o.founded||"—", o.founded?badge("external"):"")}
        ${kpi("Employees", o.employees||"—", o.employees?badge("external"):"")}
      </div>
      ${o.description?`<p class="profile-desc">${o.description}</p>`:""}
      ${people?`<div class="people">${people}</div>`:""}
      ${o.headquarters?`<p class="muted small">🏠 ${o.headquarters}</p>`:""}
    </div>

    <!-- 📈 TECHNICAL DASHBOARD -->
    <div class="card">
      <h3>📈 Technical Dashboard
        <span class="signal-pill" style="background:${sigCol}">${t.signal==='Bullish'?'🟢':t.signal==='Bearish'?'🔴':'🟡'} ${t.signal}</span></h3>
      <p class="section-explain">${t.note}</p>
      <div class="kpi-grid">
        ${kpi("20-day avg", fmt(ti.dma20))}
        ${kpi("50-day avg", fmt(ti.dma50))}
        ${kpi("100-day avg", fmt(ti.dma100))}
        ${kpi("200-day avg", fmt(ti.dma200))}
        ${kpi("RSI (14)", ti.rsi!=null?fmt(ti.rsi,1):"—")}
        ${kpi("Stochastic", ti.stochastic?(fmt(ti.stochastic.k,0)+"/"+fmt(ti.stochastic.d,0)):"—")}
        ${kpi("ATR (proxy)", fmt(ti.atr_proxy))}
        ${kpi("Rel. Volume", ti.relative_volume!=null?fmt(ti.relative_volume,2)+"x":"—")}
        ${kpi("Immediate Support", fmt(ti.immediate_support))}
        ${kpi("Immediate Resistance", fmt(ti.immediate_resistance))}
        ${kpi("Major Support", fmt(ti.major_support))}
        ${kpi("Major Resistance", fmt(ti.major_resistance))}
      </div>
      <div class="chart-wrap" style="margin-top:14px">
        <canvas id="priceChart"></canvas>
        <div class="chart-legend">
          <span><i style="background:#1f6feb"></i>Price</span>
          <span><i style="background:#138a4e"></i>50-day avg</span>
          <span><i style="background:#c4322f"></i>200-day avg</span>
        </div>
      </div>
      <div style="margin-top:12px">${t.components.map(metricRow).join("")}</div>
    </div>

    <!-- 📉 VALUATION DASHBOARD -->
    <div class="card">
      <h3>📉 Valuation Dashboard <span class="conf">Confidence: ${val.confidence}</span></h3>
      <p class="section-explain">${val.note}</p>
      ${valHtml}
      <div style="margin-top:12px">${valMethods}</div>
      <h4 style="margin:16px 0 6px">Sector peers</h4>
      <table class="peer-table"><thead><tr><th>Symbol</th><th class="num">Price</th><th class="num">P/E</th><th class="num">Mcap (bn)</th></tr></thead><tbody>${peerRows}</tbody></table>
      <h4 style="margin:16px 0 6px">Historical price context</h4>
      ${histHtml}
    </div>

    <!-- 🧠 ANALYST CONSENSUS -->
    <div class="card">
      <h3>🧠 Analyst Consensus <span class="conf">Confidence: ${ac.confidence}</span></h3>
      ${acHtml}
    </div>

    <!-- 🏦 / 💰 SMART MONEY -->
    <div class="card">
      <h3>🏦 Broker &amp; 💰 Smart Money <span class="conf">Confidence: ${r.smart_money.confidence}</span></h3>
      <div class="note warn">${r.smart_money.note}</div>
    </div>

    <!-- 📰 NEWS -->
    <div class="card">
      <h3>📰 News Intelligence <span class="conf">Confidence: ${r.news.confidence}</span></h3>
      <p class="section-explain">${r.news.note}</p>
      ${(r.news.events&&r.news.events.length)?r.news.events.map((e)=>`<div class="event">
          <div class="ev-head">${e.headline}</div>
          <div class="ev-meta">${e.source} · Impact: ${e.impact} · Confidence: ${e.confidence} ${badge(e.kind)}</div></div>`).join("")
        :`<p class="muted">No recent events parsed.</p>`}
    </div>

    <!-- 🎯 ENTRY & EXIT -->
    <div class="card">
      <h3>🎯 Entry &amp; Exit Plan</h3>
      <p class="section-explain">Levels from price structure + volatility. Educational framework, not advice.</p>
      ${planHtml}
    </div>

    <!-- ⚠️ RISKS -->
    <div class="card">
      <h3>⚠️ Risks &amp; Limitations</h3>
      <ul class="unavailable-list">${r.limitations.map(x=>`<li>${x}</li>`).join("")}</ul>
      <h4 style="margin:14px 0 6px">Fundamentals not available on free data</h4>
      <ul class="unavailable-list">${f.unavailable.map(x=>`<li>${x}</li>`).join("")}</ul>
    </div>

    <!-- SOURCES & METHODOLOGY -->
    <div class="card">
      <h3>🔎 Sources, Assumptions &amp; Methodology</h3>
      <ul class="sources">${r.sources.map((s)=>`<li><strong>${s.name}</strong> — ${s.provides}. <span class="muted">(${s.type})</span>${s.url?` · <a href="${s.url}" target="_blank" rel="noopener">link</a>`:""}</li>`).join("")}</ul>
      <h4 style="margin:14px 0 6px">Assumptions used</h4>
      <ul class="unavailable-list">${r.assumptions.map(x=>`<li>${x}</li>`).join("")}</ul>
      <div class="note">
        <div><strong>Timestamps (UTC):</strong> collected ${r.timestamps.data_collection_start} → ${r.timestamps.data_collection_end}; report ${r.timestamps.report_generated}.</div>
        <div style="margin-top:6px">Legend — ${badge("actual")} measured · ${badge("calculated")} computed · ${badge("assumption")} chosen input · ${badge("opinion")} judgement · ${badge("external")} third-party (StockAnalysis). <strong>Educational only — not financial advice.</strong></div>
      </div>
    </div>
  `;

  drawChart(hist, ti.dma50, ti.dma200);
}

function miniCell(label, val) {
  return `<div class="setup-cell"><div class="sc-label">${label}</div><div class="sc-value">${val}</div></div>`;
}

/* ------------------------------------------------------------------ */
/* canvas price chart (no libraries)                                 */
/* ------------------------------------------------------------------ */
function smaSeries(arr, period) {
  const out = new Array(arr.length).fill(null);
  let sum = 0;
  for (let i = 0; i < arr.length; i++) {
    sum += arr[i];
    if (i >= period) sum -= arr[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

function drawChart(hist, dma50, dma200) {
  const cv = document.getElementById("priceChart");
  if (!cv || !hist || !hist.points || !hist.points.length) return;
  const pts = hist.points;
  const closes = pts.map((p) => p.close);
  const ma50 = smaSeries(closes, 50);
  const ma200 = smaSeries(closes, 200);

  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = 240;
  cv.width = W * dpr; cv.height = H * dpr;
  const ctx = cv.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const padL = 46, padR = 10, padT = 12, padB = 22;
  const vals = closes.concat(ma50.filter(x=>x!=null), ma200.filter(x=>x!=null));
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
  const x = (i) => padL + (i / (closes.length - 1)) * (W - padL - padR);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);

  // grid + y labels
  ctx.strokeStyle = "#eef1f6"; ctx.fillStyle = "#9aa6b8"; ctx.font = "11px Segoe UI";
  ctx.textAlign = "right"; ctx.textBaseline = "middle";
  for (let g = 0; g <= 4; g++) {
    const v = lo + (hi - lo) * (g / 4);
    const yy = y(v);
    ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
    ctx.fillText(v.toFixed(1), padL - 6, yy);
  }

  const line = (series, color, width) => {
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath();
    let started = false;
    for (let i = 0; i < series.length; i++) {
      if (series[i] == null) continue;
      const px = x(i), py = y(series[i]);
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
    }
    ctx.stroke();
  };
  line(closes, "#1f6feb", 1.6);
  line(ma50, "#138a4e", 1.4);
  line(ma200, "#c4322f", 1.4);
}

/* ------------------------------------------------------------------ */
/* wiring                                                            */
/* ------------------------------------------------------------------ */
$("#scanBtn").addEventListener("click", startScan);
$("#searchInput").addEventListener("input", onSearch);
$("#drawerClose").addEventListener("click", closeDrawer);
$("#drawerOverlay").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    CURRENT_TAB = tab.dataset.tab;
    renderTable();
  }));
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search")) $("#searchResults").classList.add("hidden");
});

loadStatus();
