import React, { useCallback, useEffect, useRef, useState } from "react";
import { apiStatus, apiScan, apiSearch, apiDeepDive, apiHistory } from "./api.js";
import { fmt, scoreColor, recClass, MoS, ScoreBar } from "./format.jsx";
import DeepDive, { DeepDiveLoading, DeepDiveError } from "./DeepDive.jsx";

export default function App() {
  const [status, setStatus] = useState(null);
  const [statusErr, setStatusErr] = useState(false);

  const [scan, setScan] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState(null);

  const [tab, setTab] = useState("top");

  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searchOpen, setSearchOpen] = useState(false);

  // drawer / deep-dive
  const [drawerSym, setDrawerSym] = useState(null);
  const [report, setReport] = useState(null);
  const [hist, setHist] = useState(null);
  const [ddLoading, setDdLoading] = useState(false);
  const [ddError, setDdError] = useState(null);

  const searchRef = useRef(null);

  // ---- initial status ----
  useEffect(() => {
    apiStatus()
      .then(setStatus)
      .catch(() => setStatusErr(true));
  }, []);

  // ---- scan ----
  const runScan = useCallback(() => {
    setScanning(true);
    setScanError(null);
    apiScan(20)
      .then((d) => {
        setScan(d.result || d);
      })
      .catch((e) => setScanError(e.message))
      .finally(() => setScanning(false));
  }, []);

  // ---- debounced search ----
  useEffect(() => {
    const q = query.trim();
    if (q.length < 1) {
      setResults([]);
      setSearchOpen(false);
      return;
    }
    const id = setTimeout(() => {
      apiSearch(q)
        .then((d) => {
          setResults(d.results || []);
          setSearchOpen((d.results || []).length > 0);
        })
        .catch(() => setSearchOpen(false));
    }, 220);
    return () => clearTimeout(id);
  }, [query]);

  // close search dropdown on outside click
  useEffect(() => {
    const onClick = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) setSearchOpen(false);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  // ---- drawer ----
  const openStock = useCallback((symbol) => {
    setDrawerSym(symbol);
    setReport(null);
    setHist(null);
    setDdError(null);
    setDdLoading(true);
    setQuery("");
    setSearchOpen(false);
    Promise.all([apiDeepDive(symbol), apiHistory(symbol)])
      .then(([rep, h]) => {
        setReport(rep);
        setHist(h);
      })
      .catch((e) => setDdError(e.message))
      .finally(() => setDdLoading(false));
  }, []);

  const closeDrawer = useCallback(() => setDrawerSym(null), []);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") setDrawerSym(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const rows = scan ? (tab === "value" ? scan.undervalued : scan.opportunities) : [];
  const meta = scan?.meta;
  const liteN = status?.lite_scan_symbols;

  return (
    <>
      {/* ===== Header ===== */}
      <header className="topbar">
        <div className="brand">
          <div className="logo">PSX</div>
          <div>
            <h1>Investment Analyst</h1>
            <p className="tagline">Pakistan Stock Exchange — plain-English stock analysis</p>
          </div>
        </div>
        <div className="topbar-right">
          <div className="search" ref={searchRef}>
            <input
              type="text"
              placeholder="Search any stock (e.g. HBL, ENGRO, Lucky)…"
              autoComplete="off"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => results.length && setSearchOpen(true)}
            />
            {searchOpen ? (
              <div className="search-results">
                {results.map((s) => (
                  <div className="sr-item" key={s.symbol} onClick={() => openStock(s.symbol)}>
                    <span className="sr-sym">{s.symbol}</span>
                    <span className="sr-name">{s.name || ""}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <button className="btn btn-primary" onClick={runScan} disabled={scanning}>
            {scanning ? "Scanning…" : scan ? "Refresh Analysis" : "Run Analysis"}
          </button>
        </div>
      </header>

      {/* ===== Disclaimer ===== */}
      <div className="disclaimer">
        <strong>Read me first:</strong> This tool uses <em>free, delayed</em> public data from the
        PSX Data Portal. It is an educational research aid, <strong>not financial advice</strong>.
        Some professional data (full financial statements, broker activity) isn't available for
        free, so parts of the analysis are limited — the app tells you exactly where. Always do your
        own research and consider a licensed advisor before investing.
      </div>

      <main className="container">
        {/* ===== Hosted lite-scan note ===== */}
        {liteN ? (
          <div className="lite-banner">
            ☁️ <strong>Hosted edition.</strong> To stay within the serverless time limit, “Run
            Analysis” does a <strong>lite scan</strong> of the {liteN} most-liquid stocks. The full
            120-stock scan and persistent caching live in the desktop app (<code>run.py</code>).
            Single-stock deep-dives (search any symbol) are complete.
          </div>
        ) : null}

        {/* ===== Status strip ===== */}
        <section className="status-strip">
          <span>
            {statusErr ? (
              <span className="neg">Could not reach the server.</span>
            ) : scanError ? (
              <span className="neg">Scan error: {scanError}</span>
            ) : scan && meta ? (
              <>
                Analysed <strong>{meta.deep_analysed}</strong> of {meta.universe_total} tradeable
                stocks.
              </>
            ) : (
              <>
                Click <strong>Run Analysis</strong> to scan the market.
              </>
            )}
          </span>
          <span className="muted">
            {scan && meta
              ? `Generated ${meta.report_generated}`
              : status
              ? `Server time: ${status.server_time_utc} · Source: ${status.data_source}`
              : ""}
          </span>
        </section>

        {/* ===== Scan progress ===== */}
        {scanning ? (
          <section className="progress-box">
            <div className="spinner" />
            <div>
              <div>Scanning the Pakistan Stock Exchange…</div>
              <div className="progress-log muted">
                Fetching the market snapshot and deep-analysing the most-liquid names. This runs
                synchronously and can take up to a minute on a cold start.
              </div>
            </div>
          </section>
        ) : null}

        {/* ===== Legend ===== */}
        <section className="legend">
          <span className="legend-title">How to read the data:</span>
          <span className="badge badge-actual">Actual</span> real market data
          <span className="badge badge-calculated">Calculated</span> computed by the app
          <span className="badge badge-assumption">Assumption</span> an input we chose
          <span className="badge badge-opinion">Opinion</span> a judgement
        </section>

        {/* ===== Opportunities ===== */}
        {scan ? (
          <section>
            <div className="tabs">
              <button
                className={"tab" + (tab === "top" ? " active" : "")}
                onClick={() => setTab("top")}
              >
                Top Opportunities
              </button>
              <button
                className={"tab" + (tab === "value" ? " active" : "")}
                onClick={() => setTab("value")}
              >
                Trading Below Fair Value
              </button>
            </div>

            <div className="table-wrap">
              <table className="opp-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Symbol</th>
                    <th className="hide-sm">Company</th>
                    <th className="num">Price</th>
                    <th className="num">Fair Value</th>
                    <th className="num">Margin of Safety</th>
                    <th className="num">Score</th>
                    <th>Recommendation</th>
                    <th className="num hide-sm">Data</th>
                  </tr>
                </thead>
                <tbody>
                  {rows && rows.length ? (
                    rows.map((o, i) => (
                      <tr key={o.symbol} onClick={() => openStock(o.symbol)}>
                        <td>{i + 1}</td>
                        <td>
                          <span className="sym-cell">{o.symbol}</span>
                          {o.speculative ? (
                            <span
                              className="spec-tag"
                              title="Flagged speculative — thin/penny/micro-cap. Higher risk."
                            >
                              {" "}
                              ⚠
                            </span>
                          ) : null}
                        </td>
                        <td className="company-cell hide-sm">{o.name || ""}</td>
                        <td className="num">{fmt(o.price)}</td>
                        <td className="num">{fmt(o.fair_value)}</td>
                        <td className="num">
                          <MoS m={o.margin_of_safety_pct} />
                        </td>
                        <td className="num">
                          <span className="score-pill">
                            <ScoreBar s={o.investment_score} />
                            <span className="score-num" style={{ color: scoreColor(o.investment_score) }}>
                              {fmt(o.investment_score, 0)}
                            </span>
                          </span>
                        </td>
                        <td>
                          <span className={recClass(o.recommendation)}>{o.recommendation}</span>
                        </td>
                        <td className="num hide-sm muted">{o.data_coverage_pct}%</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="9" className="muted" style={{ padding: 24 }}>
                        No stocks matched this view.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="muted small">
              Weights — Fundamental 40% · Technical 25% · Fair Value 20% · Broker 10% · News 5%.
              “Data” = how much of the score rests on available data. Click any row for the full
              breakdown.
            </p>
          </section>
        ) : null}
      </main>

      {/* ===== Detail drawer ===== */}
      {drawerSym ? <div className="overlay" onClick={closeDrawer} /> : null}
      {drawerSym ? (
        <aside className="drawer">
          <button className="drawer-close" aria-label="Close" onClick={closeDrawer}>
            ×
          </button>
          <div>
            {ddLoading ? (
              <DeepDiveLoading symbol={drawerSym} />
            ) : ddError ? (
              <DeepDiveError symbol={drawerSym} message={ddError} />
            ) : report ? (
              <DeepDive report={report} hist={hist} />
            ) : null}
          </div>
        </aside>
      ) : null}

      <footer className="footer">
        <span>Data: PSX Data Portal (dps.psx.com.pk) — public, delayed.</span>
        <span>Analysis computed locally. Not financial advice.</span>
      </footer>
    </>
  );
}
