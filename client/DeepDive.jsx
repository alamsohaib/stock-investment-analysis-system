import React from "react";
import {
  fmt,
  fmtBig,
  scoreColor,
  recClass,
  signalColor,
  Badge,
  MoS,
  ScoreBar,
  Gauge,
  Kpi,
  MiniCell,
} from "./format.jsx";
import PriceChart from "./PriceChart.jsx";

function Chg({ chg }) {
  if (chg == null) return null;
  return (
    <span className={chg >= 0 ? "pos" : "neg"}>
      {chg >= 0 ? "▲" : "▼"} {fmt(Math.abs(chg), 2)}%
    </span>
  );
}

function MetricRow({ c }) {
  const v = c.value === null || c.value === undefined ? "—" : c.value;
  return (
    <div className="metric">
      <div className="m-left">
        <span className="m-label">{c.label}</span>
        {c.explain ? <span className="m-explain">{c.explain}</span> : null}
      </div>
      <div className="m-right">
        <span className="m-value">{v}</span>
        <Badge kind={c.kind} />
        {c.subscore != null ? (
          <span className="muted small">{fmt(c.subscore, 0)}/100</span>
        ) : null}
      </div>
    </div>
  );
}

const PLABELS = {
  fundamentals: "Fundamentals",
  valuation: "Valuation",
  technicals: "Technicals",
  broker_activity: "Broker / Smart Money",
  institutional_consensus: "Analyst Consensus",
  news_sentiment: "News",
};

// Loading / error placeholders shown in the drawer.
export function DeepDiveLoading({ symbol }) {
  return (
    <div className="d-head">
      <div className="spinner" style={{ margin: "40px auto" }} />
      <p className="muted" style={{ textAlign: "center" }}>
        Building institutional research report for {symbol}…
        <br />
        <span className="small">(fetching PSX + StockAnalysis data)</span>
      </p>
    </div>
  );
}

export function DeepDiveError({ symbol, message }) {
  return (
    <div className="d-head">
      <p className="neg">
        Could not analyse {symbol}: {message}
      </p>
    </div>
  );
}

export default function DeepDive({ report: r, hist }) {
  const v = r.verdict,
    mk = r.market,
    o = r.overview,
    t = r.technical,
    val = r.valuation,
    ac = r.analyst_consensus,
    f = r.fundamentals;
  const ti = t.indicators || {};
  const pl = r.plan,
    ret = r.returns;
  const hc = val.historical || {};
  const peers = val.peers || [];

  return (
    <>
      <div className="d-head">
        <div className="d-symline">
          <span className="d-sym">{r.symbol}</span>
          <span className="d-name">{r.name}</span>
          {r.external_available ? (
            <span className="src-pill">+ StockAnalysis</span>
          ) : (
            <span className="src-pill src-pill--off">PSX only</span>
          )}
        </div>
        <div className="d-symline" style={{ marginTop: 6 }}>
          <span className="d-price">Rs {fmt(r.price)}</span> <Chg chg={r.change_pct} />
        </div>
        <div className="d-sub">
          {o.sector || "—"}
          {o.industry ? " · " + o.industry : ""} · Overall confidence:{" "}
          {r.confidence_overall} · Data coverage {v.data_coverage_pct}%
        </div>
      </div>

      {/* ⭐ VERDICT */}
      <div className="card verdict-card">
        <div className="verdict-top">
          <div className="verdict-gauge">
            <Gauge score={v.overall_score} size={116} />
            <div className="muted small" style={{ textAlign: "center" }}>
              Investment Score
            </div>
          </div>
          <div className="verdict-main">
            <div className="muted small">⭐ FINAL VERDICT</div>
            <span
              className={recClass(v.recommendation)}
              style={{
                fontSize: 20,
                padding: "9px 20px",
                margin: "6px 0",
                display: "inline-block",
              }}
            >
              {v.recommendation}
            </span>
            <p className="d-sub" style={{ maxWidth: 430 }}>
              {v.action_hint} <Badge kind="opinion" />
            </p>
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          {Object.keys(v.breakdown).map((k) => (
            <div className="bd-row" key={k}>
              <span className="bd-label">{PLABELS[k] || k}</span>
              <ScoreBar s={v.breakdown[k]} w={0} />
              <span className="bd-val" style={{ color: scoreColor(v.breakdown[k]) }}>
                {fmt(v.breakdown[k], 0)}
              </span>
              <span className="bd-w">{Math.round(v.weights[k] * 100)}%</span>
            </div>
          ))}
        </div>
        <p className="muted small" style={{ marginTop: 6 }}>
          Weights — Fundamentals 35% · Valuation 25% · Technicals 15% · Broker 10% ·
          Analyst 10% · News 5%.
        </p>
        {v.speculative ? (
          <div className="note warn">
            <strong>⚠ Flagged SPECULATIVE.</strong>
            <ul className="unavailable-list">
              {(v.risk_flags || []).map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      {/* 📊 MARKET SNAPSHOT */}
      <div className="card">
        <h3>📊 Market Snapshot</h3>
        <div className="kpi-grid">
          <Kpi label="Price" val={"Rs " + fmt(mk.current_price)} sub={<Chg chg={r.change_pct} />} />
          <Kpi label="Previous Close" val={"Rs " + fmt(mk.previous_close)} />
          <Kpi label="Day Range" val={fmt(mk.day_low) + " – " + fmt(mk.day_high)} />
          <Kpi label="52-Week Range" val={fmt(mk.week52_low) + " – " + fmt(mk.week52_high)} />
          <Kpi label="Avg Volume (30d)" val={fmtBig(mk.avg_daily_volume_30d)} />
          <Kpi label="Today Volume" val={fmtBig(mk.today_volume)} />
          <Kpi label="Market Cap" val={"Rs " + fmtBig(mk.market_cap)} />
          <Kpi
            label="Dividend Yield"
            val={mk.dividend_yield_pct != null ? fmt(mk.dividend_yield_pct, 2) + "%" : "—"}
            sub={mk.dividend_yield_pct != null ? <Badge kind="external" /> : ""}
          />
          <Kpi
            label="Beta"
            val={mk.beta != null ? fmt(mk.beta, 2) : "—"}
            sub={mk.beta != null ? <Badge kind="external" /> : ""}
          />
          <Kpi label="Enterprise Value" val="—" sub="needs net debt" />
        </div>
      </div>

      {/* 🏢 COMPANY PROFILE */}
      <div className="card">
        <h3>🏢 Company Profile</h3>
        <div className="kpi-grid">
          <Kpi label="Sector" val={o.sector || "—"} />
          <Kpi label="Industry" val={o.industry || "—"} sub={o.industry ? <Badge kind="external" /> : ""} />
          <Kpi label="Shares Outstanding" val={fmtBig(o.shares_outstanding)} />
          <Kpi label="Free Float" val={o.free_float_pct != null ? fmt(o.free_float_pct, 1) + "%" : "—"} />
          <Kpi label="Founded" val={o.founded || "—"} sub={o.founded ? <Badge kind="external" /> : ""} />
          <Kpi label="Employees" val={o.employees || "—"} sub={o.employees ? <Badge kind="external" /> : ""} />
        </div>
        {o.description ? <p className="profile-desc">{o.description}</p> : null}
        {o.key_people && o.key_people.length ? (
          <div className="people">
            {o.key_people.map((p, i) => (
              <span className="person" key={i}>
                <strong>{p.name}</strong> · {p.role}
              </span>
            ))}
          </div>
        ) : null}
        {o.headquarters ? <p className="muted small">🏠 {o.headquarters}</p> : null}
      </div>

      {/* 📈 TECHNICAL DASHBOARD */}
      <div className="card">
        <h3>
          📈 Technical Dashboard{" "}
          <span className="signal-pill" style={{ background: signalColor(t.signal) }}>
            {t.signal === "Bullish" ? "🟢" : t.signal === "Bearish" ? "🔴" : "🟡"} {t.signal}
          </span>
        </h3>
        <p className="section-explain">{t.note}</p>
        <div className="kpi-grid">
          <Kpi label="20-day avg" val={fmt(ti.dma20)} />
          <Kpi label="50-day avg" val={fmt(ti.dma50)} />
          <Kpi label="100-day avg" val={fmt(ti.dma100)} />
          <Kpi label="200-day avg" val={fmt(ti.dma200)} />
          <Kpi label="RSI (14)" val={ti.rsi != null ? fmt(ti.rsi, 1) : "—"} />
          <Kpi
            label="Stochastic"
            val={ti.stochastic ? fmt(ti.stochastic.k, 0) + "/" + fmt(ti.stochastic.d, 0) : "—"}
          />
          <Kpi label="ATR (proxy)" val={fmt(ti.atr_proxy)} />
          <Kpi label="Rel. Volume" val={ti.relative_volume != null ? fmt(ti.relative_volume, 2) + "x" : "—"} />
          <Kpi label="Immediate Support" val={fmt(ti.immediate_support)} />
          <Kpi label="Immediate Resistance" val={fmt(ti.immediate_resistance)} />
          <Kpi label="Major Support" val={fmt(ti.major_support)} />
          <Kpi label="Major Resistance" val={fmt(ti.major_resistance)} />
        </div>
        <PriceChart hist={hist} />
        <div style={{ marginTop: 12 }}>
          {(t.components || []).map((c, i) => (
            <MetricRow c={c} key={i} />
          ))}
        </div>
      </div>

      {/* 📉 VALUATION DASHBOARD */}
      <div className="card">
        <h3>
          📉 Valuation Dashboard <span className="conf">Confidence: {val.confidence}</span>
        </h3>
        <p className="section-explain">{val.note}</p>
        {val.base ? (
          <div className="setup-grid">
            <div className="setup-cell">
              <div className="sc-label">Conservative</div>
              <div className="sc-value">{fmt(val.conservative)}</div>
            </div>
            <div className="setup-cell entry">
              <div className="sc-label">Base (fair)</div>
              <div className="sc-value">{fmt(val.base)}</div>
            </div>
            <div className="setup-cell">
              <div className="sc-label">Bull</div>
              <div className="sc-value">{fmt(val.bull)}</div>
            </div>
            <div className="setup-cell">
              <div className="sc-label">Margin of Safety</div>
              <div className="sc-value">
                <MoS m={val.margin_of_safety_pct} />
              </div>
            </div>
          </div>
        ) : (
          <p className="muted">Scenario fair value could not be computed (EPS unavailable).</p>
        )}
        <div style={{ marginTop: 12 }}>
          {(val.methods || []).map((mm, i) => (
            <div className="metric" key={i}>
              <div className="m-left">
                <span className="m-label">{mm.method}</span>
                <span className="m-explain">{mm.note || ""}</span>
              </div>
              <div className="m-right">
                <span className="m-value">{mm.fair_value != null ? fmt(mm.fair_value) : "n/a"}</span>
                <Badge kind={mm.kind} />
              </div>
            </div>
          ))}
        </div>
        <h4 style={{ margin: "16px 0 6px" }}>Sector peers</h4>
        <table className="peer-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="num">Price</th>
              <th className="num">P/E</th>
              <th className="num">Mcap (bn)</th>
            </tr>
          </thead>
          <tbody>
            {peers.length ? (
              peers.map((p, i) => (
                <tr key={i}>
                  <td className="sym-cell">{p.symbol}</td>
                  <td className="num">{fmt(p.price)}</td>
                  <td className="num">{p.pe != null ? fmt(p.pe, 1) : "—"}</td>
                  <td className="num">{p.market_cap_bn != null ? fmt(p.market_cap_bn, 1) : "—"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="muted">
                  No sector peers found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <h4 style={{ margin: "16px 0 6px" }}>Historical price context</h4>
        <div className="setup-grid" style={{ marginTop: 8 }}>
          <MiniCell label="1-yr avg price" val={fmt(hc.avg_1y)} />
          <MiniCell label="3-yr avg price" val={fmt(hc.avg_3y)} />
          <MiniCell label="5-yr avg price" val={fmt(hc.avg_5y)} />
        </div>
        <p className="muted small" style={{ marginTop: 6 }}>
          {hc.note || ""}
        </p>
      </div>

      {/* 🧠 ANALYST CONSENSUS */}
      <div className="card">
        <h3>
          🧠 Analyst Consensus <span className="conf">Confidence: {ac.confidence}</span>
        </h3>
        {ac.available ? (
          <>
            <div className="consensus">
              <div className={"consensus-rating " + recClass(ac.rating)}>{ac.rating}</div>
              <div className="consensus-detail">
                <div>
                  <span className="muted">12-month target:</span>{" "}
                  <strong>Rs {fmt(ac.target_price)}</strong>{" "}
                  {ac.target_upside_pct != null ? (
                    <span className={ac.target_upside_pct >= 0 ? "pos" : "neg"}>
                      ({ac.target_upside_pct >= 0 ? "+" : ""}
                      {fmt(ac.target_upside_pct, 1)}%)
                    </span>
                  ) : null}
                </div>
                <div className="muted small">{ac.source}</div>
              </div>
              <div className="consensus-gauge">
                <Gauge score={ac.score} size={80} />
              </div>
            </div>
            <div className="note">
              <Badge kind="external" /> {ac.note}
            </div>
          </>
        ) : (
          <div className="note warn">{ac.note}</div>
        )}
      </div>

      {/* 🏦 / 💰 SMART MONEY */}
      <div className="card">
        <h3>
          🏦 Broker &amp; 💰 Smart Money{" "}
          <span className="conf">Confidence: {r.smart_money.confidence}</span>
        </h3>
        <div className="note warn">{r.smart_money.note}</div>
      </div>

      {/* 📰 NEWS */}
      <div className="card">
        <h3>
          📰 News Intelligence <span className="conf">Confidence: {r.news.confidence}</span>
        </h3>
        <p className="section-explain">{r.news.note}</p>
        {r.news.events && r.news.events.length ? (
          r.news.events.map((e, i) => (
            <div className="event" key={i}>
              <div className="ev-head">{e.headline}</div>
              <div className="ev-meta">
                {e.source} · Impact: {e.impact} · Confidence: {e.confidence} <Badge kind={e.kind} />
              </div>
            </div>
          ))
        ) : (
          <p className="muted">No recent events parsed.</p>
        )}
      </div>

      {/* 🎯 ENTRY & EXIT */}
      <div className="card">
        <h3>🎯 Entry &amp; Exit Plan</h3>
        <p className="section-explain">
          Levels from price structure + volatility. Educational framework, not advice.
        </p>
        {pl.available ? (
          <>
            <div className="setup-grid">
              <div className="setup-cell entry">
                <div className="sc-label">Ideal Buy</div>
                <div className="sc-value">{fmt(pl.entry.ideal_buy)}</div>
              </div>
              <div className="setup-cell entry">
                <div className="sc-label">Accumulation Zone</div>
                <div className="sc-value">
                  {pl.accumulation_zone
                    ? fmt(pl.accumulation_zone[0]) + "–" + fmt(pl.accumulation_zone[1])
                    : fmt(pl.entry.max_buy)}
                </div>
              </div>
              <div className="setup-cell sl">
                <div className="sc-label">Stop Loss</div>
                <div className="sc-value">
                  {fmt(pl.stop_loss.price)} <span className="small">({fmt(pl.stop_loss.pct, 1)}%)</span>
                </div>
              </div>
              <div className="setup-cell">
                <div className="sc-label">Risk / Reward</div>
                <div className="sc-value">{pl.expected.risk_reward ?? "—"} : 1</div>
              </div>
            </div>
            <div className="targets">
              <div className="target">
                <div className="t-k">Target 1</div>
                <div className="t-v">{fmt(pl.targets.t1)}</div>
              </div>
              <div className="target">
                <div className="t-k">Target 2</div>
                <div className="t-v">{fmt(pl.targets.t2)}</div>
              </div>
              <div className="target">
                <div className="t-k">Target 3</div>
                <div className="t-v">{fmt(pl.targets.t3)}</div>
              </div>
            </div>
            {ret.available ? (
              <>
                <div className="setup-grid" style={{ marginTop: 10 }}>
                  <MiniCell
                    label="6-month est. return"
                    val={(ret.est_6m_pct >= 0 ? "+" : "") + fmt(ret.est_6m_pct, 1) + "%"}
                  />
                  <MiniCell
                    label="12-month est. return"
                    val={(ret.est_12m_pct >= 0 ? "+" : "") + fmt(ret.est_12m_pct, 1) + "%"}
                  />
                  <MiniCell
                    label="Volatility (annual)"
                    val={ret.volatility_pct != null ? fmt(ret.volatility_pct, 1) + "%" : "—"}
                  />
                </div>
                <p className="muted small" style={{ marginTop: 6 }}>
                  <Badge kind="opinion" /> {ret.note}
                </p>
              </>
            ) : null}
            <p className="muted small" style={{ marginTop: 8 }}>
              Horizon: {pl.horizon}
            </p>
            <div className="note warn">{pl.note}</div>
          </>
        ) : (
          <p className="muted">No trade plan available.</p>
        )}
      </div>

      {/* ⚠️ RISKS */}
      <div className="card">
        <h3>⚠️ Risks &amp; Limitations</h3>
        <ul className="unavailable-list">
          {r.limitations.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
        <h4 style={{ margin: "14px 0 6px" }}>Fundamentals not available on free data</h4>
        <ul className="unavailable-list">
          {f.unavailable.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </div>

      {/* SOURCES & METHODOLOGY */}
      <div className="card">
        <h3>🔎 Sources, Assumptions &amp; Methodology</h3>
        <ul className="sources">
          {r.sources.map((s, i) => (
            <li key={i}>
              <strong>{s.name}</strong> — {s.provides}. <span className="muted">({s.type})</span>
              {s.url ? (
                <>
                  {" "}
                  ·{" "}
                  <a href={s.url} target="_blank" rel="noopener noreferrer">
                    link
                  </a>
                </>
              ) : null}
            </li>
          ))}
        </ul>
        <h4 style={{ margin: "14px 0 6px" }}>Assumptions used</h4>
        <ul className="unavailable-list">
          {r.assumptions.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
        <div className="note">
          <div>
            <strong>Timestamps (UTC):</strong> collected {r.timestamps.data_collection_start} →{" "}
            {r.timestamps.data_collection_end}; report {r.timestamps.report_generated}.
          </div>
          <div style={{ marginTop: 6 }}>
            Legend — <Badge kind="actual" /> measured · <Badge kind="calculated" /> computed ·{" "}
            <Badge kind="assumption" /> chosen input · <Badge kind="opinion" /> judgement ·{" "}
            <Badge kind="external" /> third-party (StockAnalysis).{" "}
            <strong>Educational only — not financial advice.</strong>
          </div>
        </div>
      </div>
    </>
  );
}
