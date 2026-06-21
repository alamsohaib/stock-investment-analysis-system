"""Pipeline: screen the PSX universe, rank opportunities, build full reports."""
from __future__ import annotations

import datetime as dt
import statistics

from . import psx_client as psx
from . import analysis as an


def _now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------------------------------------------------------- #
# Screening
# --------------------------------------------------------------------------- #
def screen_universe(cfg):
    """Return tradeable equity candidates (symbol + snapshot), most liquid first."""
    u = cfg.get("universe", {})
    symbols = psx.get_symbols()
    snapshot = psx.get_market_snapshot()

    meta = {s["symbol"]: s for s in symbols}
    candidates = []
    for sym, snap in snapshot.items():
        info = meta.get(sym, {})
        if u.get("exclude_debt_instruments", True) and info.get("is_debt"):
            continue
        if u.get("exclude_etfs", False) and info.get("is_etf"):
            continue
        price = snap.get("current") or snap.get("ldcp") or 0
        if price < u.get("min_price", 1.0):
            continue
        if (snap.get("volume") or 0) < u.get("min_daily_volume", 0):
            continue
        snap = dict(snap)
        snap["sector"] = info.get("sector", "")
        candidates.append(snap)

    candidates.sort(key=lambda x: x.get("volume", 0), reverse=True)
    return candidates


# --------------------------------------------------------------------------- #
# Sector P/E medians (relative valuation anchor)
# --------------------------------------------------------------------------- #
def _sector_median_pe(companies_by_symbol, snapshot_by_symbol):
    buckets = {}
    for sym, comp in companies_by_symbol.items():
        if not comp:
            continue
        pe = comp.get("pe_ttm")
        sector = (snapshot_by_symbol.get(sym, {}) or {}).get("sector", "")
        if pe and 0 < pe < 100 and sector:
            buckets.setdefault(sector, []).append(pe)
    return {sec: statistics.median(v) for sec, v in buckets.items() if v}


# --------------------------------------------------------------------------- #
# Single-symbol full report
# --------------------------------------------------------------------------- #
def build_report(symbol, cfg, snapshot=None, sector_median_pe=None):
    symbol = symbol.upper()
    start = _now_utc()
    if snapshot is None:
        snap_all = psx.get_market_snapshot()
        snapshot = snap_all.get(symbol)
    company = psx.get_company(symbol)
    history = psx.get_history(symbol)
    sector = (snapshot or {}).get("sector") or (company or {}).get("sector", "")
    if not sector:  # single-symbol path: look it up from the cached symbol list
        for s in psx.get_symbols():
            if s["symbol"] == symbol:
                sector = s.get("sector", "")
                break
    sec_pe = None
    if sector_median_pe and sector in sector_median_pe:
        sec_pe = sector_median_pe[sector]

    fund = an.fundamental_analysis(company, snapshot, sec_pe)
    tech = an.technical_analysis(history)
    fv = an.fair_value(company, snapshot, cfg, sec_pe)
    broker = an.broker_analysis()
    news = an.news_analysis(company)
    flags = an.quality_flags(company, snapshot, cfg)
    combined = an.combine(cfg.get("scoring_weights", {}), fund, tech, fv, broker, news, flags)
    setup = an.trade_setup(tech, fv)

    price = (snapshot or {}).get("current") or (company or {}).get("close") \
        or (company or {}).get("ldcp")

    return {
        "symbol": symbol,
        "name": (company or {}).get("name") or (snapshot or {}).get("name") or symbol,
        "sector": sector,
        "price": round(price, 2) if price else None,
        "change_pct": (snapshot or {}).get("change_pct"),
        "snapshot": snapshot,
        "timestamps": {"data_start": start, "report_generated": _now_utc()},
        "fundamental": fund,
        "technical": tech,
        "fair_value": fv,
        "broker": broker,
        "news": news,
        "combined": combined,
        "trade_setup": setup,
        "sources": _sources(),
    }


def _summary_from_report(r):
    fv = r["fair_value"]
    return {
        "symbol": r["symbol"],
        "name": r["name"],
        "sector": r["sector"],
        "price": r["price"],
        "change_pct": r["change_pct"],
        "fair_value": fv.get("base"),
        "margin_of_safety_pct": fv.get("margin_of_safety_pct"),
        "investment_score": r["combined"]["investment_score"],
        "recommendation": r["combined"]["recommendation"],
        "data_coverage_pct": r["combined"]["data_coverage_pct"],
        "speculative": r["combined"].get("speculative", False),
        "fundamental_score": r["fundamental"]["score"],
        "technical_score": r["technical"]["score"],
    }


# --------------------------------------------------------------------------- #
# Full universe run (ranked opportunities)
# --------------------------------------------------------------------------- #
def run_universe(cfg, top_n=20, progress=None):
    start = _now_utc()
    candidates = screen_universe(cfg)
    limit = cfg.get("universe", {}).get("max_symbols_full_scan", 120)
    deep = candidates[:limit]
    symbols = [c["symbol"] for c in deep]
    snap_by_sym = {c["symbol"]: c for c in deep}
    workers = cfg.get("data", {}).get("max_parallel_requests", 8)

    if progress:
        progress(f"Screened {len(candidates)} tradeable stocks; deep-analysing top {len(symbols)} by liquidity…")

    # pre-fetch company + history in parallel (warms the cache)
    companies = psx.fetch_many(symbols, psx.get_company, max_workers=workers)
    psx.fetch_many(symbols, psx.get_history, max_workers=workers)
    sector_pe = _sector_median_pe(companies, snap_by_sym)

    reports, summaries = [], []
    for sym in symbols:
        try:
            r = build_report(sym, cfg, snapshot=snap_by_sym.get(sym),
                             sector_median_pe=sector_pe)
            reports.append(r)
            summaries.append(_summary_from_report(r))
        except Exception as e:  # one bad symbol must not kill the whole run
            if progress:
                progress(f"skip {sym}: {e}")

    summaries.sort(key=lambda x: (x["investment_score"] or 0), reverse=True)
    undervalued = [s for s in summaries
                   if (s["margin_of_safety_pct"] or -999) >= 0]

    return {
        "meta": {
            "data_collection_start": start,
            "report_generated": _now_utc(),
            "universe_total": len(candidates),
            "deep_analysed": len(summaries),
            "top_n": top_n,
            "sources": _sources(),
            "weights": cfg.get("scoring_weights", {}),
        },
        "opportunities": summaries[:top_n],
        "undervalued": undervalued[:top_n],
        "all_ranked": summaries,
    }


def _sources():
    return [
        {"name": "PSX Data Portal", "url": "https://dps.psx.com.pk",
         "provides": "Prices, P/E, EPS, shares, free float, 52-week range, dividends, history",
         "type": "Official, public, DELAYED data"},
        {"name": "Calculation engine (this app)",
         "provides": "Technical indicators, scores, relative fair value, trade setup",
         "type": "Computed locally"},
    ]
