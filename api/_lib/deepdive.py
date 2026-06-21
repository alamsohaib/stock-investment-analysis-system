"""Institutional-grade single-stock deep-dive report.

Composes PSX-native data + StockAnalysis external validation into the full research
report described in the brief. Single-stock mode uses its OWN weighting:
    Fundamentals 35% · Valuation 25% · Technicals 15% ·
    Broker Activity 10% · Institutional/Analyst Consensus 10% · News 5%

Honesty rules carried over: every value is tagged actual / calculated / assumption /
opinion / external; unavailable data is declared, never invented.
"""
from __future__ import annotations

import datetime as dt

from . import psx_client as psx
from . import external as extmod
from . import indicators as ind
from . import analysis as an

SINGLE_WEIGHTS = {
    "fundamentals": 0.35,
    "valuation": 0.25,
    "technicals": 0.15,
    "broker_activity": 0.10,
    "institutional_consensus": 0.10,
    "news_sentiment": 0.05,
}


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _scale(x, lo, hi):
    return an._scale(x, lo, hi)


def _clamp(x, lo, hi):
    return an._clamp(x, lo, hi)


# --------------------------------------------------------------------------- #
# Company overview  🏢
# --------------------------------------------------------------------------- #
def company_overview(symbol, company, ext, snapshot, sector):
    mcap_000 = (company or {}).get("market_cap_000")
    mcap = (ext.get("market_cap") if ext.get("available") else None) \
        or (mcap_000 * 1000 if mcap_000 else None)
    return {
        "name": (company or {}).get("name") or symbol,
        "ticker": symbol,
        "sector": sector or ext.get("sector") or "—",
        "industry": ext.get("industry") if ext.get("available") else None,
        "market_cap": mcap,
        "free_float_pct": (company or {}).get("free_float_pct"),
        "shares_outstanding": (company or {}).get("shares_outstanding")
                              or (ext.get("shares_out") if ext.get("available") else None),
        "founded": ext.get("founded") if ext.get("available") else None,
        "ipo_date": None,  # not exposed by the free sources
        "employees": ext.get("employees") if ext.get("available") else None,
        "headquarters": (company or {}).get("address"),
        "description": (company or {}).get("business_description")
                       or (ext.get("description") if ext.get("available") else None),
        "key_people": (company or {}).get("key_people", []),
        "exchange": "Pakistan Stock Exchange (PSX)",
    }


# --------------------------------------------------------------------------- #
# Market snapshot  📊
# --------------------------------------------------------------------------- #
def market_snapshot(company, snapshot, history, ext):
    snap = snapshot or {}
    price = snap.get("current") or (company or {}).get("close") or (company or {}).get("ldcp")
    closes = [h["close"] for h in history] if history else []
    vols = [h["volume"] for h in history] if history else []
    avg_vol_30 = round(sum(vols[-30:]) / len(vols[-30:])) if len(vols) >= 5 else None
    mcap_000 = (company or {}).get("market_cap_000")
    mcap = (ext.get("market_cap") if ext.get("available") else None) or (mcap_000 * 1000 if mcap_000 else None)

    return {
        "current_price": round(price, 2) if price else None,
        "previous_close": snap.get("ldcp") or (company or {}).get("ldcp"),
        "change_pct": snap.get("change_pct"),
        "day_high": snap.get("high") or (company or {}).get("high"),
        "day_low": snap.get("low") or (company or {}).get("low"),
        "week52_high": ((company or {}).get("week52") or {}).get("high"),
        "week52_low": ((company or {}).get("week52") or {}).get("low"),
        "avg_daily_volume_30d": avg_vol_30,
        "today_volume": snap.get("volume") or (company or {}).get("volume"),
        "market_cap": mcap,
        "enterprise_value": None,  # needs net debt (not on free feed)
        "ev_note": "Enterprise Value needs total debt & cash, which are not on the free feed.",
        "dividend_yield_pct": ext.get("dividend_yield_pct") if ext.get("available") else None,
        "beta": ext.get("beta") if ext.get("available") else None,
    }


# --------------------------------------------------------------------------- #
# Enhanced fundamentals  (PSX + StockAnalysis)
# --------------------------------------------------------------------------- #
def enhanced_fundamentals(company, ext, snapshot, sector_pe):
    price = (snapshot or {}).get("current") or (company or {}).get("close") or (company or {}).get("ldcp")
    pe = (company or {}).get("pe_ttm") or (ext.get("pe_ratio") if ext.get("available") else None)
    comps, scores = [], []
    has_ext = ext.get("available")

    if pe and pe > 0:
        comps.append({"label": "P/E Ratio (TTM)", **an.m(round(pe, 2), "actual"),
                      "explain": "Price paid per rupee of trailing earnings.",
                      "subscore": round(_scale(pe, 20, 4), 1)})
        scores.append((0.30, _scale(pe, 20, 4)))
        if sector_pe:
            comps.append({"label": "P/E vs sector median", **an.m(round(pe / sector_pe, 2), "calculated"),
                          "explain": f"Sector median ~{round(sector_pe,1)}. Below 1.0 = cheaper than peers."})
            scores.append((0.10, _scale(pe / sector_pe, 1.6, 0.5)))

    if has_ext:
        fpe = ext.get("forward_pe")
        if fpe:
            comps.append({"label": "Forward P/E", **an.m(round(fpe, 2), "external"),
                          "explain": "Based on expected next-year earnings (StockAnalysis)."})
        nm = ext.get("net_margin_pct")
        if nm is not None:
            comps.append({"label": "Net Profit Margin", **an.m(f"{nm}%", "external"),
                          "explain": "Profit kept from each rupee of sales. Higher = stronger business."})
            scores.append((0.20, _scale(nm, 2, 35)))
        rg = ext.get("revenue_growth")
        if rg is not None:
            comps.append({"label": "Revenue Growth (YoY)", **an.m(f"{rg}%", "external"),
                          "explain": "Sales growth vs a year ago."})
            scores.append((0.12, _scale(rg, -15, 30)))
        eg = ext.get("eps_growth")
        if eg is not None:
            comps.append({"label": "Earnings (EPS) Growth", **an.m(f"{eg}%", "external"),
                          "explain": "Profit-per-share growth vs a year ago."})
            scores.append((0.13, _scale(eg, -20, 30)))
        dy = ext.get("dividend_yield_pct")
        if dy is not None:
            comps.append({"label": "Dividend Yield", **an.m(f"{dy}%", "external"),
                          "explain": "Annual dividend as a % of price."})
            scores.append((0.10, _scale(dy, 0, 10)))
        pr = ext.get("payout_ratio_pct")
        if pr is not None:
            comps.append({"label": "Payout Ratio", **an.m(f"{pr}%", "external"),
                          "explain": "Share of earnings paid as dividends. Very high (>90%) can be risky."})

    ff = (company or {}).get("free_float_pct")
    if ff:
        comps.append({"label": "Free Float", **an.m(f"{round(ff,1)}%", "actual"),
                      "explain": "Higher = more liquid, harder to manipulate."})
        scores.append((0.08, _scale(ff, 10, 60)))

    total_w = sum(w for w, _ in scores) or 1.0
    score = sum(w * s for w, s in scores) / total_w if scores else 50.0
    confidence = "Medium-High" if has_ext else ("Low" if pe else "Very Low")

    missing = ["ROE / ROA / ROIC", "Gross & operating margins",
               "Debt-to-Equity, interest coverage, current ratio",
               "Free cash flow & FCF yield", "Book value (P/B, PEG)"]
    return {
        "score": round(score, 1), "confidence": confidence, "components": comps,
        "unavailable": missing,
        "note": ("Merges PSX data with StockAnalysis fundamentals (revenue, earnings, "
                 "margins, growth). Deeper balance-sheet ratios remain unavailable on free "
                 "sources and are listed below — not estimated."),
    }


# --------------------------------------------------------------------------- #
# Analyst / institutional consensus  🧠
# --------------------------------------------------------------------------- #
_CONSENSUS_SCORE = {"strong buy": 92, "buy": 78, "accumulate": 70, "outperform": 75,
                    "hold": 50, "neutral": 50, "underperform": 30, "reduce": 32, "sell": 18}


def analyst_consensus(ext):
    if not ext.get("available") or not ext.get("analyst_consensus"):
        return {"available": False, "score": 50.0, "confidence": "None",
                "note": ("No aggregated analyst consensus available for this PSX symbol. "
                         "PSX brokerage-house ratings (AKD, Topline, etc.) are not free.")}
    word = ext["analyst_consensus"]
    base = _CONSENSUS_SCORE.get(word.lower(), 50)
    up = ext.get("analyst_target_upside_pct")
    # nudge by target upside
    if up is not None:
        base = _clamp(base + _clamp(up, -20, 20) * 0.5, 0, 100)
    return {
        "available": True, "score": round(base, 1), "confidence": "Medium",
        "rating": word,
        "target_price": ext.get("analyst_target_price"),
        "target_upside_pct": up,
        "source": "StockAnalysis (aggregated analyst data)",
        "note": ("External aggregated analyst rating & 12-month price target. Treat as "
                 "supporting evidence — analyst targets are frequently revised."),
    }


# --------------------------------------------------------------------------- #
# Broker activity / smart money  💰  (unavailable on free data)
# --------------------------------------------------------------------------- #
def smart_money():
    return {
        "available": False, "score": 50.0, "confidence": "None",
        "broker_flow": None, "institutional": None, "insider": None,
        "note": ("Broker-wise flow, institutional holdings (mutual/pension funds, foreign "
                 "investors) and insider/director transactions are NOT published on free "
                 "sources. This pillar is neutral (50/100) and does not bias the verdict. "
                 "A paid broker/CDC feed would enable real smart-money tracking."),
    }


# --------------------------------------------------------------------------- #
# Advanced valuation  📉
# --------------------------------------------------------------------------- #
def advanced_valuation(company, ext, snapshot, history, cfg, sector_pe, peers):
    price = (snapshot or {}).get("current") or (company or {}).get("close") or (company or {}).get("ldcp")
    eps = (ext.get("eps_ttm") if ext.get("available") else None) or (company or {}).get("eps_ttm")
    fv_cfg = cfg.get("fair_value", {})
    min_pe, max_pe = fv_cfg.get("min_target_pe", 4.0), fv_cfg.get("max_target_pe", 15.0)

    # --- scenario valuation (assumption-driven; NOT a statement-based DCF) ---
    cons = base = bull = None
    g = (ext.get("eps_growth") if ext.get("available") else None) or 0.0
    g = _clamp(g, -10, 25) / 100.0
    if eps and eps > 0:
        anchor = sector_pe or 8.0
        base_pe = _clamp(anchor, min_pe, max_pe)
        cons = base_pe * 0.8 * eps * (1 + min(g, 0.05))
        base = base_pe * eps * (1 + g)
        bull = base_pe * 1.2 * eps * (1 + g + 0.05)

    capped = False
    if base and price:
        cap = price * fv_cfg.get("max_fair_to_price", 2.5)
        if base > cap:
            capped = True
            base = cap
            cons, bull = min(cons, cap * 0.85), min(bull, cap * 1.15)

    mos = round((base - price) / base * 100, 1) if (base and price) else None
    over_under = round((price - base) / base * 100, 1) if (base and price) else None

    # --- historical price context (1/3/5-year average close) ---
    closes = [h["close"] for h in history] if history else []
    def avg_last(n):
        w = closes[-n:]
        return round(sum(w) / len(w), 2) if len(w) >= max(20, n // 4) else None
    hist_ctx = {
        "avg_1y": avg_last(252), "avg_3y": avg_last(756), "avg_5y": avg_last(1260),
        "note": ("Compares price to its OWN historical average price (mean-reversion "
                 "context). Historical P/E is not available — no historical EPS on free feed."),
    }

    methods = [
        {"method": "Scenario valuation (target P/E × EPS × growth)", "kind": "calculated",
         "fair_value": round(base, 2) if base else None,
         "note": "Conservative/Base/Bull below. Assumption-driven, not a cash-flow DCF."},
        {"method": "Relative — sector median P/E", "kind": "calculated",
         "fair_value": round((sector_pe or 0) * eps, 2) if (sector_pe and eps) else None,
         "note": f"Sector median P/E ~ {round(sector_pe,1) if sector_pe else 'n/a'}."},
        {"method": "Discounted Cash Flow (statement-based)", "kind": "assumption",
         "fair_value": None,
         "note": "NOT COMPUTED — needs free cash flow & full statements (unavailable free)."},
    ]
    if ext.get("available") and ext.get("analyst_target_price"):
        methods.append({"method": "Analyst price target (external cross-check)", "kind": "external",
                        "fair_value": ext["analyst_target_price"],
                        "note": "StockAnalysis aggregated 12-month target."})

    score = _scale(mos, -40, 40) if mos is not None else 50.0
    confidence = "Very Low" if capped else ("Low-Medium" if base else "Very Low")
    extra = ""
    if capped:
        extra = (" NOTE: fair value CAPPED — raw estimate was several times the price, "
                 "usually a sign of one-off/unsustainable earnings (P/E near 1).")

    return {
        "score": round(score, 1), "confidence": confidence, "capped": capped,
        "current_price": round(price, 2) if price else None,
        "conservative": round(cons, 2) if cons else None,
        "base": round(base, 2) if base else None,
        "bull": round(bull, 2) if bull else None,
        "fair_value_range": [round(cons, 2), round(bull, 2)] if (cons and bull) else None,
        "margin_of_safety_pct": mos, "over_under_valued_pct": over_under,
        "methods": methods, "historical": hist_ctx, "peers": peers,
        "note": ("Relative & scenario valuation only — treat as a sanity check, not a price "
                 "target." + extra),
    }


# --------------------------------------------------------------------------- #
# Technical dashboard  📈
# --------------------------------------------------------------------------- #
def technical_dashboard(history, snapshot):
    base = an.technical_analysis(history)
    closes = [h["close"] for h in history] if history else []
    inds = base.get("indicators", {})
    if len(closes) >= 30:
        stoch = ind.stochastic(closes)
        inds["stochastic"] = stoch
        # immediate vs major support / resistance
        imm = ind.support_resistance(closes, 20)
        maj = ind.support_resistance(closes, 250)
        inds["immediate_support"] = imm["support"]
        inds["immediate_resistance"] = imm["resistance"]
        inds["major_support"] = maj["support"]
        inds["major_resistance"] = maj["resistance"]
        base["indicators"] = inds
        if stoch:
            base["components"].append({"label": "Stochastic %K/%D",
                                       **an.m(f"{stoch['k']} / {stoch['d']}", "calculated"),
                                       "explain": "Below 20 = oversold, above 80 = overbought (close-based approx)."})

    s = base["score"]
    signal = "Bullish" if s >= 60 else ("Bearish" if s < 42 else "Neutral")
    base["signal"] = signal
    base["signal_color"] = {"Bullish": "green", "Neutral": "amber", "Bearish": "red"}[signal]
    return base


# --------------------------------------------------------------------------- #
# News intelligence  📰
# --------------------------------------------------------------------------- #
def news_intelligence(company, ext):
    events = []
    for a in (company or {}).get("dividend_announcements", []):
        events.append({"headline": f"Dividend / payout announcement: {a}",
                       "source": "PSX Data Portal", "date": "recent",
                       "impact": "Bullish", "confidence": "Medium", "kind": "actual"})
    if ext.get("available"):
        if ext.get("earnings_date"):
            events.append({"headline": f"Next earnings expected: {ext['earnings_date']}",
                           "source": "StockAnalysis", "date": ext["earnings_date"],
                           "impact": "Neutral (event)", "confidence": "Medium", "kind": "external"})
        if ext.get("ex_dividend_date"):
            events.append({"headline": f"Ex-dividend date: {ext['ex_dividend_date']}"
                                       + (f" (DPS {ext.get('dps')})" if ext.get('dps') else ""),
                           "source": "StockAnalysis", "date": ext["ex_dividend_date"],
                           "impact": "Bullish", "confidence": "Medium", "kind": "external"})
    score = 60.0 if events else 50.0
    return {"available": bool(events), "score": score, "confidence": "Low", "events": events,
            "note": ("Built from PSX announcements + StockAnalysis event dates. Wide-web news "
                     "sentiment (M&A, policy, sector) is not scanned in this free build.")}


# --------------------------------------------------------------------------- #
# Decision framework + return estimates + entry/exit
# --------------------------------------------------------------------------- #
def decide(funds, val, tech, broker, consensus, news, flags):
    w = SINGLE_WEIGHTS
    parts = {
        "fundamentals": (w["fundamentals"], funds["score"]),
        "valuation": (w["valuation"], val["score"]),
        "technicals": (w["technicals"], tech["score"]),
        "broker_activity": (w["broker_activity"], broker["score"]),
        "institutional_consensus": (w["institutional_consensus"], consensus["score"]),
        "news_sentiment": (w["news_sentiment"], news["score"]),
    }
    tw = sum(p[0] for p in parts.values())
    score = sum(p[0] * p[1] for p in parts.values()) / tw
    if flags.get("penalty"):
        score = max(0.0, score - flags["penalty"])

    rec, action = an.recommendation(score, tech["score"], val.get("margin_of_safety_pct"))
    if flags.get("speculative") and rec in ("Strong Buy", "Buy"):
        rec = "Accumulate"
        action = "Cheap-looking but flagged SPECULATIVE — small size only, if at all."

    # data coverage
    informative = 0.0
    if funds["confidence"] not in ("Very Low",): informative += w["fundamentals"]
    if val["confidence"] not in ("Very Low",): informative += w["valuation"]
    if tech["confidence"] not in ("Very Low",): informative += w["technicals"]
    if broker.get("available"): informative += w["broker_activity"]
    if consensus.get("available"): informative += w["institutional_consensus"]
    if news.get("available"): informative += w["news_sentiment"]

    return {
        "overall_score": round(score, 1), "recommendation": rec, "action_hint": action,
        "data_coverage_pct": round(informative / tw * 100),
        "speculative": flags.get("speculative", False), "risk_flags": flags.get("reasons", []),
        "weights": {k: parts[k][0] for k in parts},
        "breakdown": {k: round(parts[k][1], 1) for k in parts},
    }


def return_estimates(price, val, consensus, tech):
    if not price:
        return {"available": False}
    # Prefer the analyst's forward 12-month target (a real return view). Fall back to
    # the relative margin-of-safety only when no analyst target exists. (A sector-relative
    # "premium/discount" is a weak return predictor on its own.)
    if consensus.get("available") and consensus.get("target_upside_pct") is not None:
        blended = consensus["target_upside_pct"]
        if val.get("margin_of_safety_pct") is not None:
            blended = 0.7 * blended + 0.3 * _clamp(val["margin_of_safety_pct"], -30, 30)
    elif val.get("margin_of_safety_pct") is not None:
        blended = _clamp(val["margin_of_safety_pct"], -40, 40)
    else:
        blended = None
    vol = (tech.get("indicators") or {}).get("realized_vol_pct")
    return {
        "available": blended is not None,
        "est_12m_pct": round(blended, 1) if blended is not None else None,
        "est_6m_pct": round(blended * 0.55, 1) if blended is not None else None,
        "volatility_pct": vol,
        "kind": "opinion",
        "note": ("Blends fair-value margin of safety with the analyst target (where "
                 "available). An estimate under uncertainty, NOT a promise."),
    }


def entry_exit(tech, val):
    setup = an.trade_setup(tech, {"base": val.get("base"), "optimistic": val.get("bull")})
    if setup.get("available"):
        inds = tech.get("indicators", {})
        imm_s = inds.get("immediate_support")
        if imm_s:
            setup["accumulation_zone"] = [round(imm_s, 2), round(setup["entry"]["max_buy"], 2)]
        setup["max_acceptable_risk_pct"] = abs(setup["stop_loss"]["pct"])
    return setup


# --------------------------------------------------------------------------- #
# Peers
# --------------------------------------------------------------------------- #
def sector_peers(symbol, sector, cfg, limit=5):
    if not sector:
        return []
    snap = psx.get_market_snapshot()
    syms = psx.get_symbols()
    same = [s["symbol"] for s in syms
            if s.get("sector") == sector and not s.get("is_debt") and s["symbol"] != symbol]
    # rank by liquidity using snapshot volume
    same = [s for s in same if s in snap]
    same.sort(key=lambda s: snap[s].get("volume", 0), reverse=True)
    chosen = same[:limit]
    comps = psx.fetch_many(chosen, psx.get_company,
                           max_workers=cfg.get("data", {}).get("max_parallel_requests", 8))
    peers = []
    for s in chosen:
        c = comps.get(s) or {}
        peers.append({
            "symbol": s, "name": c.get("name") or s,
            "price": (snap.get(s) or {}).get("current"),
            "pe": c.get("pe_ttm"),
            "market_cap_bn": round(c["market_cap_000"] / 1_000_000, 1) if c.get("market_cap_000") else None,
        })
    return peers


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def build_deepdive(symbol, cfg, sector_median_pe=None):
    symbol = symbol.upper()
    start = _now()

    snap_all = psx.get_market_snapshot()
    snapshot = snap_all.get(symbol)
    company = psx.get_company(symbol)
    history = psx.get_history(symbol)
    ext = extmod.get_stockanalysis(symbol)

    sector = (snapshot or {}).get("sector") or ""
    if not sector:
        for s in psx.get_symbols():
            if s["symbol"] == symbol:
                sector = s.get("sector", "")
                break
    sec_pe = (sector_median_pe or {}).get(sector) if sector_median_pe else None

    peers = sector_peers(symbol, sector, cfg)
    # derive sector P/E from peers if we don't have one
    if not sec_pe:
        pes = [p["pe"] for p in peers if p.get("pe") and 0 < p["pe"] < 100]
        if pes:
            sec_pe = sorted(pes)[len(pes) // 2]

    overview = company_overview(symbol, company, ext, snapshot, sector)
    snap_block = market_snapshot(company, snapshot, history, ext)
    funds = enhanced_fundamentals(company, ext, snapshot, sec_pe)
    val = advanced_valuation(company, ext, snapshot, history, cfg, sec_pe, peers)
    tech = technical_dashboard(history, snapshot)
    consensus = analyst_consensus(ext)
    broker = smart_money()
    news = news_intelligence(company, ext)
    flags = an.quality_flags(company, snapshot, cfg)
    verdict = decide(funds, val, tech, broker, consensus, news, flags)
    price = snap_block["current_price"]
    returns = return_estimates(price, val, consensus, tech)
    plan = entry_exit(tech, val)

    sources = [
        {"name": "PSX Data Portal", "url": "https://dps.psx.com.pk",
         "provides": "Price, P/E, EPS, shares, free float, 52wk, dividends, history, profile",
         "type": "Official PSX — public, DELAYED"},
    ]
    if ext.get("available"):
        sources.append({"name": "StockAnalysis (External Validation)", "url": ext.get("url"),
                        "provides": "Revenue, net income, growth, forward P/E, margins, "
                                    "analyst consensus & target, dividend yield, beta, profile",
                        "type": "External third-party — supporting evidence only"})

    assumptions = [
        f"Target P/E anchored to sector median (~{round(sec_pe,1) if sec_pe else 'n/a'}), clamped {cfg['fair_value']['min_target_pe']}–{cfg['fair_value']['max_target_pe']}.",
        f"Earnings growth from external EPS growth, clamped to [-10%, +25%].",
        f"Fair value capped at {cfg['fair_value']['max_fair_to_price']}× price to avoid earnings-artifact mirages.",
        "Stop-loss/targets from price structure + ATR proxy (close-based; no intraday H/L on free feed).",
    ]
    limitations = [
        "Delayed free data — not for intraday decisions.",
        "No statement-based DCF, ROE/ROA, gross/operating margins, D/E (full statements not free).",
        "No broker-wise flow, institutional holdings or insider transactions (not free).",
        "No wide-web news sentiment; only PSX/StockAnalysis events.",
        "External data (StockAnalysis) is third-party and may differ from audited PSX filings.",
    ]
    if not ext.get("available"):
        limitations.insert(0, f"StockAnalysis external data unavailable for {symbol} "
                              f"({ext.get('note','')}) — fundamentals are PSX-only and limited.")

    return {
        "symbol": symbol, "name": overview["name"], "sector": sector,
        "price": price, "change_pct": snap_block["change_pct"],
        "external_available": ext.get("available", False),
        "timestamps": {"data_collection_start": start, "data_collection_end": _now(),
                       "report_generated": _now()},
        "overview": overview,
        "market": snap_block,
        "fundamentals": funds,
        "valuation": val,
        "technical": tech,
        "analyst_consensus": consensus,
        "smart_money": broker,
        "news": news,
        "verdict": verdict,
        "returns": returns,
        "plan": plan,
        "sources": sources,
        "assumptions": assumptions,
        "limitations": limitations,
        "confidence_overall": _overall_confidence(funds, val, tech, ext),
    }


def _overall_confidence(funds, val, tech, ext):
    pts = 0
    if ext.get("available"): pts += 2
    if funds["confidence"] in ("Medium-High", "Medium"): pts += 1
    if tech["confidence"] == "High": pts += 1
    if not val.get("capped"): pts += 1
    return "High" if pts >= 4 else ("Medium" if pts >= 2 else "Low")
