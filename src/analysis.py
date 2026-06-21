"""Analysis engine: turns raw PSX data into scores, fair value, a recommendation
and a trade setup.

Design principle (from the project brief): NEVER present an estimate as a fact.
Every number carries a `kind` tag so the UI can colour-code it:
    actual      -> measured market data (price, P/E, volume)
    calculated  -> computed from actual data (RSI, scores, fair value)
    assumption  -> an input we chose (discount rate, target multiple)
    opinion     -> a judgement (recommendation, thesis)
And every block carries a confidence level the user can see.
"""
from __future__ import annotations

from . import indicators as ind


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def m(value, kind, note=""):
    """Wrap a metric with its provenance so the UI can be honest about it."""
    return {"value": value, "kind": kind, "note": note}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _scale(x, lo, hi):
    """Map x in [lo,hi] -> 0..100 (clamped)."""
    if hi == lo:
        return 50.0
    return _clamp((x - lo) / (hi - lo) * 100.0, 0.0, 100.0)


# --------------------------------------------------------------------------- #
# 1. FUNDAMENTAL
# --------------------------------------------------------------------------- #
def fundamental_analysis(company, snapshot, sector_median_pe=None):
    price = (snapshot or {}).get("current") or (company or {}).get("close") \
        or (company or {}).get("ldcp")
    pe = (company or {}).get("pe_ttm")
    eps = (company or {}).get("eps_ttm")
    ff = (company or {}).get("free_float_pct")
    mcap_000 = (company or {}).get("market_cap_000")
    wk = (company or {}).get("week52")
    pays_div = bool((company or {}).get("dividend_announcements"))

    components = []
    scores = []  # (weight, score)

    # --- valuation: P/E (lower is cheaper). Healthy range ~ 4 (cheap) .. 20 (rich)
    if pe and pe > 0:
        # invert: pe 4 -> 100, pe 20 -> 0
        pe_score = _scale(pe, 20, 4)
        components.append({"label": "P/E Ratio (TTM)", **m(round(pe, 2), "actual"),
                           "subscore": round(pe_score, 1),
                           "explain": "Lower P/E generally means you pay less per rupee of earnings."})
        scores.append((0.40, pe_score))
        if sector_median_pe:
            rel = pe / sector_median_pe if sector_median_pe else None
            components.append({"label": "P/E vs sector median",
                               **m(round(rel, 2) if rel else None, "calculated"),
                               "explain": f"Sector median P/E ~ {round(sector_median_pe,1)}. "
                                          "Below 1.0 = cheaper than peers."})
            if rel:
                scores.append((0.10, _scale(rel, 1.6, 0.5)))

    # --- earnings yield (1/PE) vs a high local risk-free rate (assumption)
    if pe and pe > 0:
        ey = 100.0 / pe
        components.append({"label": "Earnings Yield", **m(round(ey, 2), "calculated", "= 1 / P/E, in %"),
                           "explain": "Company's earnings as a % of its price. Compare to T-bill yields."})
        scores.append((0.20, _scale(ey, 5, 25)))

    # --- dividend behaviour (we can see announcements, not the rupee amount on free tier)
    components.append({"label": "Pays dividends",
                       **m("Yes" if pays_div else "Not seen recently", "actual",
                           "From PSX corporate-action announcements."),
                       "explain": "Regular dividends are a sign of real, distributable profit."})
    scores.append((0.10, 70.0 if pays_div else 45.0))

    # --- free float / liquidity quality
    if ff:
        components.append({"label": "Free Float", **m(f"{round(ff,1)}%", "actual"),
                           "explain": "Higher free float = easier to buy/sell, less manipulation risk."})
        scores.append((0.10, _scale(ff, 10, 60)))

    # --- size (market cap, '000 PKR -> bn)
    if mcap_000:
        mcap_bn = mcap_000 / 1_000_000.0
        components.append({"label": "Market Cap", **m(f"{round(mcap_bn,1)} bn PKR", "calculated"),
                           "explain": "Larger companies are usually more stable and better covered."})
        scores.append((0.10, _scale(mcap_bn, 2, 200)))

    # --- where price sits in its 52-week range (value vs froth)
    if wk and price and wk.get("high") and wk.get("low") and wk["high"] != wk["low"]:
        pos = (price - wk["low"]) / (wk["high"] - wk["low"])
        components.append({"label": "Position in 52-week range",
                           **m(f"{round(pos*100)}%", "calculated"),
                           "explain": "Lower in the range can mean better value (but check why it fell)."})
        # mild preference for lower-but-not-collapsing
        scores.append((0.10, _scale(pos, 0.95, 0.15)))

    total_w = sum(w for w, _ in scores) or 1.0
    score = sum(w * s for w, s in scores) / total_w if scores else 50.0

    # confidence: capped because income statement / balance sheet are unavailable free
    have = sum(1 for c in components if c.get("value") not in (None, "Not seen recently"))
    confidence = "Low" if have <= 2 else ("Medium" if have <= 4 else "Medium-High")
    if eps is None and pe is None:
        confidence = "Very Low"

    missing = [
        "Revenue & revenue growth", "Net income & earnings growth", "ROE / ROA / ROIC",
        "Gross / operating / net margins", "Debt-to-Equity & interest coverage",
        "Free cash flow & FCF yield", "Book value (P/B, PEG)",
    ]

    return {
        "score": round(score, 1),
        "confidence": confidence,
        "components": components,
        "unavailable": missing,
        "note": ("Scored only on metrics published on the FREE PSX feed (price, P/E, EPS, "
                 "free float, dividends, market cap). Full financial statements are not "
                 "free, so deep ratios are not computed — they are listed as unavailable."),
    }


# --------------------------------------------------------------------------- #
# 2. TECHNICAL
# --------------------------------------------------------------------------- #
def technical_analysis(history):
    closes = [h["close"] for h in history] if history else []
    vols = [h["volume"] for h in history] if history else []
    if len(closes) < 30:
        return {"score": 50.0, "confidence": "Very Low",
                "components": [], "indicators": {},
                "note": "Not enough price history for reliable technical analysis."}

    price = closes[-1]
    d20, d50 = ind.sma(closes, 20), ind.sma(closes, 50)
    d100, d200 = ind.sma(closes, 100), ind.sma(closes, 200)
    rsi = ind.rsi(closes, 14)
    macd = ind.macd(closes)
    boll = ind.bollinger(closes)
    atr = ind.atr_proxy(closes)
    vol_pct = ind.realized_vol_pct(closes)
    relvol = ind.relative_volume(vols)
    sr = ind.support_resistance(closes, 60)

    components, scores = [], []

    # trend: price vs moving averages
    above = sum(1 for ma in (d20, d50, d100, d200) if ma and price > ma)
    trend_score = _scale(above, 0, 4)
    components.append({"label": "Trend (price vs 20/50/100/200-day avg)",
                       **m(f"above {above} of 4", "calculated"),
                       "explain": "Above more averages = stronger uptrend."})
    scores.append((0.30, trend_score))

    # moving-average alignment (golden vs death)
    if d50 and d200:
        aligned = d50 > d200
        components.append({"label": "50-day vs 200-day",
                           **m("Bullish (golden)" if aligned else "Bearish (death)", "calculated"),
                           "explain": "50-day above 200-day is a classic long-term uptrend signal."})
        scores.append((0.15, 75.0 if aligned else 30.0))

    # RSI momentum
    if rsi is not None:
        # reward 45-65 (healthy), penalise >75 (overbought) and <30 (falling knife)
        if rsi >= 75:
            rs = 35.0
        elif rsi <= 25:
            rs = 30.0
        else:
            rs = _scale(rsi, 25, 60)
        components.append({"label": "RSI (14)", **m(round(rsi, 1), "calculated"),
                           "explain": "Below 30 = oversold, above 70 = overbought. ~50-60 is healthy momentum."})
        scores.append((0.20, rs))

    # MACD
    if macd:
        bull = macd["histogram"] > 0
        components.append({"label": "MACD", **m(("Bullish" if bull else "Bearish")
                                                + f" (hist {macd['histogram']})", "calculated"),
                           "explain": "Histogram above zero = upward momentum building."})
        scores.append((0.20, 70.0 if bull else 35.0))

    # Bollinger position
    if boll and boll.get("percent_b") is not None:
        pb = boll["percent_b"]
        components.append({"label": "Bollinger %B", **m(round(pb, 2), "calculated"),
                           "explain": "0 = at lower band (cheap), 1 = at upper band (stretched)."})
        scores.append((0.15, _scale(pb, 1.1, 0.1)))

    # volume confirmation
    if relvol is not None:
        components.append({"label": "Relative Volume", **m(f"{relvol}x avg", "calculated"),
                           "explain": "Above 1x means unusually active trading today."})

    score = (sum(w * s for w, s in scores) / sum(w for w, _ in scores)) if scores else 50.0

    indicators = {
        "price": round(price, 2),
        "dma20": round(d20, 2) if d20 else None,
        "dma50": round(d50, 2) if d50 else None,
        "dma100": round(d100, 2) if d100 else None,
        "dma200": round(d200, 2) if d200 else None,
        "rsi": rsi, "macd": macd, "bollinger": boll,
        "atr_proxy": atr, "realized_vol_pct": vol_pct,
        "relative_volume": relvol, "support": sr["support"], "resistance": sr["resistance"],
    }
    return {
        "score": round(score, 1),
        "confidence": "High" if len(closes) >= 200 else "Medium",
        "components": components,
        "indicators": indicators,
        "note": ("Based on real daily CLOSE history. ATR is approximated from close-to-close "
                 "moves because intraday highs/lows are not in the free feed."),
    }


# --------------------------------------------------------------------------- #
# 3. FAIR VALUE  (relative / multiples based — DCF needs unavailable statements)
# --------------------------------------------------------------------------- #
def fair_value(company, snapshot, cfg, sector_median_pe=None):
    price = (snapshot or {}).get("current") or (company or {}).get("close") \
        or (company or {}).get("ldcp")
    eps = (company or {}).get("eps_ttm")
    pe = (company or {}).get("pe_ttm")
    fv_cfg = cfg.get("fair_value", {})
    min_pe = fv_cfg.get("min_target_pe", 4.0)
    max_pe = fv_cfg.get("max_target_pe", 15.0)

    methods = []
    base = cons = opt = None

    if eps and eps > 0:
        # anchor target P/E to sector median (or a neutral market multiple of 8),
        # clamped to a sane band. This is RELATIVE valuation, not DCF.
        anchor = sector_median_pe if sector_median_pe else 8.0
        target_pe = _clamp(anchor, min_pe, max_pe)
        base = target_pe * eps
        cons = target_pe * 0.75 * eps
        opt = target_pe * 1.25 * eps
        methods.append({
            "method": "Relative valuation (target P/E × EPS)",
            "kind": "calculated",
            "inputs": {"eps_ttm": round(eps, 2), "target_pe": round(target_pe, 2),
                       "anchor_pe": round(anchor, 2)},
            "fair_value": round(base, 2),
            "note": "Assumes the stock should trade near a fair multiple of its trailing earnings.",
        })

    # DCF & DDM are explicitly NOT computed (inputs unavailable on free tier)
    methods.append({
        "method": "Discounted Cash Flow (DCF)", "kind": "assumption",
        "fair_value": None,
        "note": "NOT COMPUTED — requires free cash flow & financial statements, "
                "which are not on the free PSX feed.",
    })
    methods.append({
        "method": "Dividend Discount Model (DDM)", "kind": "assumption",
        "fair_value": None,
        "note": "NOT COMPUTED — requires rupee dividend-per-share history, "
                "not exposed on the free feed (only announcement labels are).",
    })

    # sanity cap: a "fair value" several times the price almost always means the
    # trailing earnings are non-recurring (P/E near 1). Cap it and flag it rather
    # than dangling a fantasy 4x target in front of the user.
    capped = False
    if base and price:
        cap = price * fv_cfg.get("max_fair_to_price", 2.5)
        if base > cap:
            capped = True
            base = cap
            cons = min(cons, cap * 0.8)
            opt = min(opt, cap * 1.1)

    margin_of_safety = None
    discount_premium = None
    if base and price:
        margin_of_safety = round((base - price) / base * 100, 1)   # +ve = undervalued
        discount_premium = round((price - base) / base * 100, 1)   # +ve = trading at premium

    # score: more undervaluation -> higher
    if margin_of_safety is not None:
        score = _scale(margin_of_safety, -40, 40)
    else:
        score = 50.0

    confidence = "Low-Medium" if base else "Very Low"
    extra_note = ""
    if capped:
        confidence = "Very Low"
        extra_note = (" NOTE: fair value was CAPPED — the raw estimate was several times the "
                      "price, which usually means the trailing earnings are one-off/unsustainable "
                      "(P/E near 1). Do not treat this as a reliable bargain.")

    return {
        "score": round(score, 1),
        "confidence": confidence,
        "capped": capped,
        "conservative": round(cons, 2) if cons else None,
        "base": round(base, 2) if base else None,
        "optimistic": round(opt, 2) if opt else None,
        "current_price": round(price, 2) if price else None,
        "margin_of_safety_pct": margin_of_safety,
        "discount_premium_pct": discount_premium,
        "methods": methods,
        "note": ("Fair value here is RELATIVE (multiples-based), not an absolute DCF. "
                 "Treat it as a sanity check, not a precise target." + extra_note),
    }


# --------------------------------------------------------------------------- #
# 4. BROKER  (honestly unavailable on free tier)
# --------------------------------------------------------------------------- #
def broker_analysis():
    return {
        "score": 50.0,  # neutral placeholder — does not push the recommendation
        "confidence": "None",
        "available": False,
        "components": [],
        "note": ("Broker-wise / institutional trading activity is NOT published on the free "
                 "PSX feed. This block is neutral (50/100) and does not bias the result. "
                 "Connect a paid broker-data feed to enable real smart-money analysis."),
    }


# --------------------------------------------------------------------------- #
# 5. NEWS / SENTIMENT (from PSX corporate announcements we can see)
# --------------------------------------------------------------------------- #
def news_analysis(company):
    anns = (company or {}).get("dividend_announcements") or []
    events = []
    for a in anns:
        events.append({
            "headline": f"Dividend / payout announcement: {a}",
            "source": "PSX Data Portal — company announcements",
            "kind": "actual",
            "impact": "Positive (signals distributable profit)",
            "confidence": "Medium",
        })
    score = 60.0 if events else 50.0
    return {
        "score": score,
        "confidence": "Low",
        "available": bool(events),
        "events": events,
        "note": ("Only PSX corporate announcements are used. Full news-sentiment scanning "
                 "(M&A, earnings surprises, policy) needs a news API and is not wired into "
                 "the free build — treat sentiment as indicative only."),
    }


# --------------------------------------------------------------------------- #
# 5b. QUALITY / SPECULATION GATE
# --------------------------------------------------------------------------- #
def quality_flags(company, snapshot, cfg):
    """Flag thin / penny / micro-cap stocks. The relative fair-value model can wildly
    overstate cheap, illiquid names, so we tag them, penalise the score, and cap the
    recommendation. Honours the brief's 'exclude speculative stocks' requirement."""
    q = cfg.get("quality", {})
    price = (snapshot or {}).get("current") or (company or {}).get("close") \
        or (company or {}).get("ldcp")
    ff = (company or {}).get("free_float_pct")
    mcap_000 = (company or {}).get("market_cap_000")
    mcap_bn = (mcap_000 / 1_000_000.0) if mcap_000 else None
    pe = (company or {}).get("pe_ttm")

    reasons = []
    low_pe_artifact = False
    if pe is not None and 0 < pe < cfg.get("fair_value", {}).get("suspect_low_pe", 2.5):
        reasons.append(f"Suspiciously low P/E ({round(pe,2)}) — earnings likely one-off/unsustainable")
        low_pe_artifact = True
    if price is not None and price < q.get("min_quality_price", 3.0):
        reasons.append(f"Very low share price (Rs {round(price,2)}) — penny-stock risk")
    if ff is not None and ff < q.get("min_free_float_pct", 15.0):
        reasons.append(f"Low free float ({round(ff,1)}%) — easy to manipulate / illiquid")
    if mcap_bn is not None and mcap_bn < q.get("min_market_cap_bn", 2.0):
        reasons.append(f"Small market cap ({round(mcap_bn,1)} bn) — higher risk, less coverage")
    if not (company or {}).get("dividend_announcements"):
        reasons.append("No recent dividends seen")

    # speculative if multiple flags, OR a clear earnings artifact (low P/E) plus anything
    speculative = len(reasons) >= 2 or (low_pe_artifact and len(reasons) >= 1)
    return {"speculative": speculative, "reasons": reasons,
            "penalty": (len(reasons) * q.get("speculation_penalty_per_flag", 6.0)
                        if speculative else 0.0)}


# --------------------------------------------------------------------------- #
# 6. COMBINE -> investment score + recommendation
# --------------------------------------------------------------------------- #
def combine(weights, fund, tech, fv, broker, news, flags=None):
    parts = {
        "fundamental": (weights.get("fundamental", 0.40), fund["score"], fund["confidence"]),
        "technical": (weights.get("technical", 0.25), tech["score"], tech["confidence"]),
        "fair_value": (weights.get("fair_value", 0.20), fv["score"], fv["confidence"]),
        "broker": (weights.get("broker", 0.10), broker["score"], broker["confidence"]),
        "news_sentiment": (weights.get("news_sentiment", 0.05), news["score"], news["confidence"]),
    }
    total_w = sum(w for w, _, _ in parts.values()) or 1.0
    score = sum(w * s for w, s, _ in parts.values()) / total_w

    # speculation penalty (thin/penny/micro-cap names get knocked down)
    flags = flags or {"speculative": False, "reasons": [], "penalty": 0.0}
    if flags.get("penalty"):
        score = max(0.0, score - flags["penalty"])

    # how much of the score rests on real (non-neutral / available) data
    informative = 0.0
    if fund["confidence"] not in ("Very Low",):
        informative += weights.get("fundamental", 0.40)
    if tech["confidence"] not in ("Very Low",):
        informative += weights.get("technical", 0.25)
    if fv["confidence"] not in ("Very Low",):
        informative += weights.get("fair_value", 0.20)
    if broker["confidence"] not in ("None",):
        informative += weights.get("broker", 0.10)
    if news["available"]:
        informative += weights.get("news_sentiment", 0.05)
    coverage = round(informative / total_w * 100)

    rec, action = recommendation(score, tech["score"], fv.get("margin_of_safety_pct"))

    # speculative names are capped at 'Accumulate' no matter how good the score looks
    if flags.get("speculative") and rec in ("Strong Buy", "Buy"):
        rec = "Accumulate"
        action = ("Looks cheap, but flagged SPECULATIVE — treat with caution and only a "
                  "small position, if any. See the risk flags below.")

    return {
        "investment_score": round(score, 1),
        "recommendation": rec,
        "action_hint": action,
        "data_coverage_pct": coverage,
        "speculative": flags.get("speculative", False),
        "risk_flags": flags.get("reasons", []),
        "weights_used": {k: parts[k][0] for k in parts},
        "breakdown": {k: {"score": parts[k][1], "confidence": parts[k][2],
                          "weight": parts[k][0]} for k in parts},
    }


def recommendation(score, tech_score, mos):
    """Score-based band with a couple of common-sense guardrails."""
    if score >= 80:
        rec = "Strong Buy"
    elif score >= 70:
        rec = "Buy"
    elif score >= 60:
        rec = "Accumulate"
    elif score >= 45:
        rec = "Hold"
    elif score >= 35:
        rec = "Reduce"
    else:
        rec = "Sell"

    # guardrail: don't shout "Buy" into a strong downtrend
    if rec in ("Strong Buy", "Buy") and tech_score is not None and tech_score < 35:
        rec = "Accumulate"
    # guardrail: clearly overvalued caps enthusiasm
    if mos is not None and mos < -25 and rec in ("Strong Buy", "Buy", "Accumulate"):
        rec = "Hold"

    actions = {
        "Strong Buy": "High-conviction buy candidate (still verify the data limits below).",
        "Buy": "Attractive — consider building a position.",
        "Accumulate": "Buy gradually / on dips rather than all at once.",
        "Hold": "Fairly valued — hold if owned, wait for a better entry if not.",
        "Reduce": "Consider trimming exposure.",
        "Sell": "Weak profile — consider exiting.",
    }
    return rec, actions[rec]


# --------------------------------------------------------------------------- #
# 7. TRADE SETUP
# --------------------------------------------------------------------------- #
def trade_setup(tech, fv):
    inds = tech.get("indicators", {})
    price = inds.get("price")
    if not price:
        return {"available": False, "note": "No price available for a trade setup."}

    support = inds.get("support") or round(price * 0.92, 2)
    resistance = inds.get("resistance") or round(price * 1.10, 2)
    atr = inds.get("atr_proxy") or round(price * 0.03, 2)

    ideal_buy = round(min(price, max(support * 1.01, price * 0.97)), 2)
    max_buy = round(price * 1.02, 2)

    # stop: below support, padded by ~1.5x ATR proxy, but cap the loss at ~12%
    raw_stop = min(support - 1.5 * atr, price * 0.88)
    stop = round(max(raw_stop, price * 0.80), 2)
    stop_pct = round((stop - ideal_buy) / ideal_buy * 100, 1)

    fv_base = fv.get("base")
    fv_opt = fv.get("optimistic")
    t1 = round(max(resistance, price * 1.08), 2)
    t2 = round(fv_base, 2) if fv_base and fv_base > t1 else round(price * 1.18, 2)
    t3 = round(fv_opt, 2) if fv_opt and fv_opt > t2 else round(price * 1.30, 2)

    upside = round((t2 - ideal_buy) / ideal_buy * 100, 1)
    risk = ideal_buy - stop
    reward = t2 - ideal_buy
    rr = round(reward / risk, 2) if risk > 0 else None

    # horizon hint
    rsi = inds.get("rsi")
    if rr and rr >= 2.5:
        horizon = "Medium Term (3–12 months)"
    elif rsi and rsi < 35:
        horizon = "Short Term (1–3 months) bounce, or Long Term accumulation"
    else:
        horizon = "Long Term (1–5 years)"

    return {
        "available": True,
        "entry": {"ideal_buy": ideal_buy, "max_buy": max_buy, "kind": "calculated"},
        "stop_loss": {"price": stop, "pct": stop_pct, "kind": "calculated"},
        "targets": {"t1": t1, "t2": t2, "t3": t3, "kind": "calculated"},
        "expected": {"upside_pct_to_t2": upside, "risk_reward": rr, "kind": "calculated"},
        "horizon": horizon,
        "note": ("Levels are derived from recent support/resistance and a volatility (ATR) "
                 "proxy. They are a starting framework, not financial advice — always size "
                 "positions to your own risk tolerance."),
    }
