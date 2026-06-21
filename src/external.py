"""External validation client — StockAnalysis (stockanalysis.com).

stockanalysis.com publishes fundamentals for PSX-listed stocks that the free PSX
feed does NOT expose: revenue & earnings (with growth), forward P/E, an analyst
consensus + price target, dividend yield, payout ratio, beta, industry, employees,
founding year and a business description.

Per the project brief, this data is:
  * clearly tagged as "External Validation Source: StockAnalysis",
  * kept SEPARATE from PSX-native data,
  * treated as supporting evidence — never blindly trusted.

The values are embedded in the page as a JavaScript object (Next.js stream), e.g.
    marketCap:"790.57B",revenue:"139.48B",netIncome:"68.57B",eps:"57.11",
    peRatio:"11.53",forwardPE:"9.32",analysts:"Buy",target:"759.40 (+15.33%)" ...
so we parse it with targeted regexes rather than a brittle HTML table walk.
"""
from __future__ import annotations

import re
import gzip
import urllib.request
import urllib.error

from . import cache

BASE = "https://stockanalysis.com/quote/psx/"

# PSX symbols that StockAnalysis lists under a different ticker (renames, etc.)
_ALIAS = {
    "ENGRO": "ENGROH",   # Engro Corp renamed to Engro Holdings
}
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA, "Accept": "text/html,*/*", "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


_SUFFIX = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _num(val):
    """'790.57B' -> 790570000000.0 ; '57.11' -> 57.11 ; '2.52%' -> 2.52 ; None on fail."""
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("%", "")
    if s in ("", "-", "void 0", "null", "n/a", "N/A"):
        return None
    mult = 1.0
    if s and s[-1] in _SUFFIX:
        mult = _SUFFIX[s[-1]]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _grab(text, key):
    """Pull key:"value" or key:number from the embedded JS object."""
    m = re.search(re.escape(key) + r':"([^"]*)"', text)
    if m:
        return m.group(1)
    m = re.search(re.escape(key) + r':(-?[0-9.eE+]+)', text)
    if m:
        return m.group(1)
    return None


def _info_table(text):
    """Parse infoTable:[{t:"Industry",v:"Oil & Gas"},...] -> dict."""
    out = {}
    block = re.search(r"infoTable:\[(.*?)\]", text, re.S)
    if not block:
        return out
    for mt in re.finditer(r't:"([^"]+)",v:(?:"([^"]*)"|([0-9.]+))', block.group(1)):
        label = mt.group(1)
        val = mt.group(2) if mt.group(2) not in (None, "") else mt.group(3)
        out[label] = val
    return out


def _parse_target(raw):
    """'759.40 (+15.33%)' -> (759.40, 15.33)."""
    if not raw:
        return None, None
    price = _num(re.split(r"\s", raw)[0])
    up = None
    m = re.search(r"\(([-+]?[0-9.]+)%\)", raw)
    if m:
        up = float(m.group(1))
    return price, up


def get_stockanalysis(symbol, ttl=21600):
    """Return a dict of external fundamentals, or {'available': False, ...} on miss."""
    symbol = symbol.upper()
    key = f"sa:{symbol}"
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit

    sa_ticker = _ALIAS.get(symbol, symbol)
    url = f"{BASE}{sa_ticker}/"
    try:
        html = _fetch(url)
    except urllib.error.HTTPError as e:
        # 404 = this PSX symbol genuinely has no StockAnalysis page -> cache it.
        result = {"available": False, "source": "StockAnalysis", "url": url,
                  "note": f"No StockAnalysis page for this PSX symbol (HTTP {e.code})."}
        if e.code == 404:
            cache.set(key, result)
        return result
    except (urllib.error.URLError, TimeoutError) as e:
        # transient network problem -> do NOT cache, so it retries next time.
        return {"available": False, "source": "StockAnalysis", "url": url,
                "note": f"Could not reach stockanalysis.com ({e})."}

    # the marketCap anchor must exist for the page to be a real quote
    if "marketCap" not in html:
        result = {"available": False, "source": "StockAnalysis", "url": url,
                  "note": "stockanalysis.com has no data page for this PSX symbol."}
        cache.set(key, result)
        return result

    info = _info_table(html)
    tgt_price, tgt_up = _parse_target(_grab(html, "target"))
    desc = _grab(html, "description")

    revenue = _num(_grab(html, "revenue"))
    net_income = _num(_grab(html, "netIncome"))
    net_margin = round(net_income / revenue * 100, 1) if (revenue and net_income) else None

    result = {
        "available": True,
        "source": "StockAnalysis",
        "url": url,
        "market_cap": _num(_grab(html, "marketCap")),
        "market_cap_growth": _num(_grab(html, "marketCapGrowth")),
        "revenue_ttm": revenue,
        "revenue_growth": _num(_grab(html, "revenueGrowth")),
        "net_income_ttm": net_income,
        "net_income_growth": _num(_grab(html, "netIncomeGrowth")),
        "net_margin_pct": net_margin,
        "shares_out": _num(_grab(html, "sharesOut")),
        "eps_ttm": _num(_grab(html, "eps")),
        "eps_growth": _num(_grab(html, "epsGrowth")),
        "pe_ratio": _num(_grab(html, "peRatio")),
        "forward_pe": _num(_grab(html, "forwardPE")),
        "beta": _num(_grab(html, "beta")),
        "dividend_yield_pct": _num(_grab(html, "dividendYield")),
        "dps": _num(_grab(html, "dps")),
        "payout_ratio_pct": _num(_grab(html, "payoutRatio")),
        "payout_frequency": _grab(html, "payoutFrequency"),
        "ex_dividend_date": _grab(html, "exDividendDate"),
        "earnings_date": _grab(html, "earningsDate"),
        "change_1y_pct": _num(_grab(html, "ch1y")),
        "analyst_consensus": _grab(html, "analysts"),       # e.g. "Buy"
        "analyst_target_price": tgt_price,
        "analyst_target_upside_pct": tgt_up,
        "industry": info.get("Industry"),
        "sector": info.get("Sector"),
        "founded": info.get("Founded"),
        "employees": info.get("Employees"),
        "exchange": info.get("Stock Exchange"),
        "description": desc,
    }
    cache.set(key, result)
    return result
