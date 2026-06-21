# PSX Investment Analyst

A simple, honest **stock analysis dashboard for the Pakistan Stock Exchange (PSX)**.
It scans the market, ranks opportunities, and gives a plain-English buy/hold/sell view
for each stock — with the maths, the data sources, and the *limitations* all shown openly.

> ⚠️ **This is an educational research tool, not financial advice.** It uses **free, delayed**
> public data. Always do your own research and consider a licensed advisor before investing.

---

## 1. How to start it (for everyone)

You need **Python** installed (it's free). If you don't have it, get it from
<https://www.python.org/downloads/> and during install tick **“Add Python to PATH”**.

Then:

- **Windows:** double-click **`Start PSX Analyst.bat`**.
- **Any system / terminal:** open this folder and run `python run.py`.

A browser window opens automatically at <http://127.0.0.1:8800>. Keep the small black
window (or terminal) open while you use it. To stop, close that window or press `Ctrl+C`.

**No installation of extra packages is required.** The whole app is built on Python's
built-in libraries, so there's nothing to `pip install` and nothing to break.

---

## 2. How to use the dashboard

1. Click **Run Analysis**. It scans the most actively-traded PSX stocks (takes ~1 minute).
2. Look at **Top Opportunities** — ranked best-first by an overall *Investment Score (0–100)*.
3. Switch to **Trading Below Fair Value** to see stocks the model thinks are cheap.
4. **Click any row** to open a full deep-dive: summary, fundamentals, technicals, fair value,
   a price chart, news/announcements, and a suggested entry / stop-loss / target setup.
5. Use the **search box** (top right) to analyse *any* PSX stock by symbol or name.
6. **Click any stock** (from the table or search) to open the **institutional deep-dive** —
   a full research terminal for that one company (see section 9).

### Reading the colour tags
Every number is labelled so you know how much to trust it:

| Tag | Meaning |
|-----|---------|
| 🟢 **Actual** | Real market data (price, P/E, volume) |
| 🔵 **Calculated** | Worked out by the app from real data (RSI, scores, fair value) |
| 🟡 **Assumption** | An input *we chose* (e.g. a target valuation multiple) |
| 🟣 **Opinion** | A judgement (the recommendation, the thesis) |

A **⚠ next to a symbol** means it's flagged **speculative** (penny / thin / micro-cap) —
higher risk, and the fair-value estimate is far less reliable.

---

## 3. What the scores mean

**Investment Score (0–100)** is a weighted blend, exactly as specified:

| Pillar | Weight | What it measures |
|--------|:------:|------------------|
| Fundamental | 40% | Valuation (P/E, earnings yield), dividends, size, free float, 52-week position |
| Technical | 25% | Trend (20/50/100/200-day averages), RSI, MACD, Bollinger, volume |
| Fair Value | 20% | How far the price is below/above an estimated fair value |
| Broker | 10% | *(see limitations — neutral on free data)* |
| News / Sentiment | 5% | PSX corporate announcements (dividends, payouts) |

**Recommendation bands:** `Strong Buy` ≥80 · `Buy` ≥70 · `Accumulate` ≥60 ·
`Hold` ≥45 · `Reduce` ≥35 · `Sell` <35. Two safety guardrails apply: we won't shout
“Buy” into a strong downtrend, and speculative stocks are capped at “Accumulate”.

---

## 4. Where the data comes from

**Primary source:** the official **PSX Data Portal** — <https://dps.psx.com.pk> — public and **delayed**.

**External validation source (deep-dive only):** **StockAnalysis** — <https://stockanalysis.com> —
a third-party site that *does* publish PSX fundamentals the official free feed lacks. It is
clearly tagged **External** (teal badge) in the report, kept separate from PSX-native data,
and treated as supporting evidence — never blindly trusted.

| We CAN get (free) | Source | We still CANNOT get (free) — and never fake |
|---|---|---|
| Prices, OHLC, volume, 52-week range, history | PSX | Full financial statements (balance sheet / cash-flow) |
| P/E (TTM), EPS, market cap, shares, free float | PSX | True statement-based DCF (free cash flow) |
| Dividend & payout announcements, company profile | PSX | ROE / ROA / ROIC, gross/operating margins, Debt-to-Equity |
| Revenue, net income, growth, net margin | StockAnalysis | Broker-wise / institutional / insider trading flow |
| Forward P/E, beta, dividend yield, payout ratio | StockAnalysis | Wide-web real-time news sentiment |
| **Analyst consensus rating + 12-month price target** | StockAnalysis | PSX brokerage-house (AKD, Topline…) individual ratings |

Where a metric isn't available, the app **says so** and either leaves it blank or marks
the section low-confidence. It does **not** invent numbers. This is why some stocks show
a lower "Data coverage %". If StockAnalysis has no page for a symbol, the deep-dive falls
back to PSX-only data and tells you so.

---

## 5. Institutional Deep-Dive (single-stock report)

Click any stock to open a Bloomberg-style research terminal with:

- ⭐ **Final Verdict** — overall score gauge, recommendation, and a 6-pillar breakdown
  (single-stock weights: **Fundamentals 35% · Valuation 25% · Technicals 15% ·
  Broker 10% · Analyst Consensus 10% · News 5%**)
- 📊 **Market Snapshot** — price, ranges, volumes, market cap, dividend yield, beta
- 🏢 **Company Profile** — sector, industry, founded, employees, key people, HQ, description
- 📈 **Technical Dashboard** — 20/50/100/200-day averages, RSI, MACD, Stochastic, ATR,
  immediate & major support/resistance, a Bullish/Neutral/Bearish signal, and a price chart
- 📉 **Valuation Dashboard** — conservative/base/bull scenarios, margin of safety,
  sector-peer comparison table, and historical price context (1/3/5-year averages)
- 🧠 **Analyst Consensus** — external rating + 12-month price target with upside
- 🏦💰 **Broker / Smart Money** — honestly marked unavailable on free data
- 📰 **News Intelligence** — PSX announcements + upcoming earnings / ex-dividend dates
- 🎯 **Entry & Exit Plan** — entry/accumulation zone, stop-loss, three targets,
  risk/reward, and 6- & 12-month return estimates
- ⚠️ **Risks & Limitations**, plus full **Sources, Assumptions, Timestamps & Methodology**

---

## 6. How fair value is calculated (and its limits)

The free feed has no cash-flow statements, so a true **DCF is not computed** (it's shown
as "not computed" on purpose). Instead we use **relative valuation**:

```
Fair Value (base) = target P/E × EPS
   target P/E = the stock's sector median P/E, clamped to a sane 4–15 range
   conservative = 0.75 × base      optimistic = 1.25 × base
```

**Important safety cap:** if the raw estimate comes out at more than **2.5× the current
price**, it's capped and flagged — because a "4x bargain" on free data almost always means
the trailing earnings were a one-off (a P/E near 1), not a real opportunity.

`Margin of Safety % = (Fair Value − Price) ÷ Fair Value`. Positive = potentially undervalued.

---

## 7. Make it your own (optional)

Open **`config.json`** in Notepad to tweak, then restart:

- `scoring_weights` — change the 40/25/20/10/5 blend.
- `universe.max_symbols_full_scan` — how many stocks to deep-analyse (default 120; higher = slower).
- `universe.min_daily_volume` / `min_price` — filter out illiquid/penny names.
- `quality.*` — thresholds for the speculative flag.
- `fair_value.*` — valuation multiples and the safety cap.

### Plugging in better data later
If you ever get a **paid PSX data feed** (real-time prices, financial statements,
broker activity), only one file needs changing: **`src/psx_client.py`**. Fill in the
currently-`None` fields (revenue, net income, equity, debt, free cash flow, broker data)
and the analysis layer will automatically use them — enabling true DCF, ROE/margins,
and real broker "smart-money" analysis.

---

## 8. What's inside (for the curious)

```
run.py                  ← start here
Start PSX Analyst.bat   ← Windows double-click launcher
config.json             ← all your settings
src/
  psx_client.py         ← fetches & parses PSX data + company profile (stdlib only)
  external.py           ← StockAnalysis client (external validation fundamentals)
  indicators.py         ← technical indicators incl. Stochastic (pure Python)
  analysis.py           ← screening scores, fair value, quality gate, trade setup
  deepdive.py           ← institutional single-stock report composition
  pipeline.py           ← screen the market → rank opportunities → build reports
  server.py             ← local web server + JSON API (/api/scan, /api/deepdive…)
  cache.py              ← keeps things fast & polite to data sources
web/                    ← the dashboard (HTML/CSS/JS, no build step)
data/cache/             ← cached data (safe to delete anytime)
```

---

## 9. Honest limitations (please read)

- **Delayed, free data** — not suitable for intraday trading decisions.
- **No deep fundamentals** — without financial statements, fundamental analysis is partial.
  Treat the Fundamental score as a *screen*, not a verdict.
- **Relative fair value only** — it's a sanity check, not a precise price target.
- **No broker / smart-money data** on the free tier.
- **News is limited** to PSX announcements; it does not scan the wider web.
- Scores and setups are **algorithmic opinions**. Markets are uncertain. Never invest money
  you can't afford to lose, and size positions to your own risk tolerance.

*Data: PSX Data Portal (dps.psx.com.pk). Analysis computed locally. Not financial advice.*
