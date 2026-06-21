"""PSX Data Portal client — standard library only.

Source of truth: https://dps.psx.com.pk  (official PSX Data Portal, public, delayed).

Endpoints used (verified live):
  GET /symbols                     -> JSON list of every listed symbol + sector + flags
  GET /market-watch                -> HTML table: full-market snapshot (LDCP/O/H/L/Current/Chg/Vol)
  GET /company/<SYM>               -> HTML company page: P/E, EPS, shares, free float, 52wk, dividends
  GET /timeseries/eod/<SYM>        -> JSON [[epoch, close, volume, prevClose], ...] daily history
  GET /timeseries/int/<SYM>        -> JSON intraday ticks

IMPORTANT honesty notes baked into the data:
  * This is DELAYED public data, not a real-time licensed feed.
  * Full financial statements (for true DCF / ROE / margins / D-E) and broker-wise
    activity are NOT published here for free, so those fields come back as None and
    the analysis layer marks them "data unavailable" rather than inventing numbers.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import cache

BASE = "https://dps.psx.com.pk"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# Low-level fetch
# --------------------------------------------------------------------------- #
def _fetch(path: str, timeout: int = 25) -> str:
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/json,*/*",
            "Accept-Encoding": "gzip, deflate",
            "Referer": BASE + "/",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _num(text):
    """Parse a PSX-formatted number ('1,466,852' / '6.97' / '-') -> float | None."""
    if text is None:
        return None
    s = str(text).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "N/A", "n/a", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Symbol universe
# --------------------------------------------------------------------------- #
def get_symbols(ttl=86400):
    """Full list of listed instruments. Returns list of dicts."""
    key = "symbols"
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit
    data = json.loads(_fetch("/symbols"))
    out = []
    for it in data:
        out.append(
            {
                "symbol": it.get("symbol"),
                "name": (it.get("name") or "").strip(),
                "sector": (it.get("sectorName") or "").strip(),
                "is_etf": bool(it.get("isETF")),
                "is_debt": bool(it.get("isDebt")),
            }
        )
    cache.set(key, out)
    return out


# --------------------------------------------------------------------------- #
# Market-wide snapshot (one request for the whole market)
# --------------------------------------------------------------------------- #
_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_SYM_RE = re.compile(r'data-search="([^"]+)".*?data-title="([^"]*)"', re.S)
_ORDER_RE = re.compile(r'data-order="(-?[0-9.]+)"')


def get_market_snapshot(ttl=600):
    """Parse /market-watch into {SYMBOL: {ldcp, open, high, low, current, change,
    change_pct, volume}}. One HTTP call covers the entire market."""
    key = "market_snapshot"
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit

    html = _fetch("/market-watch")
    body_idx = html.find("tbl__body")
    if body_idx < 0:
        body_idx = 0
    body = html[body_idx:]

    snap = {}
    for rowmatch in _ROW_RE.finditer(body):
        row = rowmatch.group(1)
        sm = _SYM_RE.search(row)
        if not sm:
            continue
        symbol = sm.group(1).strip()
        title = sm.group(2).strip()
        orders = _ORDER_RE.findall(row)
        # data-order numeric columns in order:
        # 0 ldcp, 1 open, 2 high, 3 low, 4 current, 5 change, 6 change%, 7 volume
        nums = [float(x) for x in orders]
        if len(nums) < 8:
            continue
        snap[symbol] = {
            "symbol": symbol,
            "name": title,
            "ldcp": nums[0],
            "open": nums[1],
            "high": nums[2],
            "low": nums[3],
            "current": nums[4],
            "change": nums[5],
            "change_pct": nums[6],
            "volume": nums[7],
        }
    cache.set(key, snap)
    return snap


# --------------------------------------------------------------------------- #
# Per-company fundamentals + corporate actions
# --------------------------------------------------------------------------- #
_STAT_RE = re.compile(
    r'class="stats_label">([^<]+)</div>\s*<div class="stats_value">([^<]*)'
)
_PE_RE = re.compile(r"P/E Ratio \(TTM\)[^<]*</div><div class=\"stats_value\">([^<]*)")
_SHARES_RE = re.compile(r">Shares</div><div class=\"stats_value\">([^<]*)")
_FF_RE = re.compile(r">Free Float</div><div class=\"stats_value\">([^<]*)")
_MCAP_RE = re.compile(r"Market Cap[^<]*</div></div><div class=\"stats_value\">([^<]*)")
_NAME_RE = re.compile(r'<div class="quote__name">([^<]+)</div>')
_SECTOR_RE = re.compile(r'<div class="quote__sector">([^<]+)</div>')
# dividend / payout rows in the announcements table
_DIV_RE = re.compile(
    r"Dividend\s+([DFIQ]-?\d{4}[^<]*)</td>", re.S
)


def _strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def _parse_profile(html):
    """Pull BUSINESS DESCRIPTION, KEY PEOPLE and ADDRESS from the company profile."""
    out = {"description": None, "people": [], "address": None}

    m = re.search(r"BUSINESS DESCRIPTION</div>\s*<p>(.*?)</p>", html, re.S)
    if m:
        out["description"] = _strip_tags(m.group(1))

    pm = re.search(r"KEY PEOPLE</div>(.*?)</table>", html, re.S)
    if pm:
        for name, role in re.findall(r"<td><strong>([^<]+)</strong></td><td>([^<]*)</td>", pm.group(1)):
            out["people"].append({"name": name.strip(), "role": role.strip()})

    am = re.search(r"ADDRESS</div>\s*(?:<p>)?(.*?)(?:</p>|</div>)", html, re.S)
    if am:
        addr = _strip_tags(am.group(1))
        if addr:
            out["address"] = addr[:240]
    return out


def get_company(symbol: str, ttl=3600):
    """Scrape the company page for the fundamentals available on the free tier."""
    symbol = symbol.upper()
    key = f"company:{symbol}"
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit

    try:
        html = _fetch(f"/company/{symbol}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    stats = {}
    for label, value in _STAT_RE.findall(html):
        label = re.sub(r"\s+", " ", label).strip().rstrip("*^ ").strip()
        # keep the FIRST occurrence (current-day panel) for OHLC-style repeats
        if label not in stats:
            stats[label] = _num(value)

    def stat(*names):
        for n in names:
            if n in stats and stats[n] is not None:
                return stats[n]
        return None

    pe = _num(_PE_RE.search(html).group(1)) if _PE_RE.search(html) else None
    shares = _num(_SHARES_RE.search(html).group(1)) if _SHARES_RE.search(html) else None
    mcap = _num(_MCAP_RE.search(html).group(1)) if _MCAP_RE.search(html) else None
    name = _NAME_RE.search(html).group(1).strip() if _NAME_RE.search(html) else symbol

    # free float can be absolute shares and/or a percentage
    ff_matches = _FF_RE.findall(html)
    free_float_pct = None
    for v in ff_matches:
        if "%" in v:
            free_float_pct = _num(v)

    # 52-week range "160.05 — 369.99"
    wk52 = None
    m = re.search(r"52-WEEK RANGE[^<]*</div><div class=\"stats_value\">([^<]*)", html)
    if m:
        parts = re.split(r"[—–-]", m.group(1))
        nums = [_num(p) for p in parts if _num(p) is not None]
        if len(nums) >= 2:
            wk52 = {"low": min(nums), "high": max(nums)}

    # recent dividend / payout announcements (corporate actions we CAN see)
    dividends = []
    for d in _DIV_RE.findall(html):
        dividends.append(re.sub(r"\s+", " ", d).strip())
    dividends = dividends[:8]

    # ---- company profile (business description, key people, address) ----
    profile = _parse_profile(html)

    result = {
        "symbol": symbol,
        "name": name,
        "pe_ttm": pe,
        "shares_outstanding": shares,
        "market_cap_000": mcap,            # PSX reports market cap in thousands
        "free_float_pct": free_float_pct,
        "open": stat("Open"),
        "high": stat("High"),
        "low": stat("Low"),
        "close": stat("Close"),
        "ldcp": stat("LDCP"),
        "volume": stat("Volume"),
        "week52": wk52,
        "dividend_announcements": dividends,
        "business_description": profile.get("description"),
        "key_people": profile.get("people", []),
        "address": profile.get("address"),
        # ---- explicitly unavailable on the free tier (never invented) ----
        "revenue": None,
        "net_income": None,
        "total_equity": None,
        "total_debt": None,
        "free_cash_flow": None,
        "operating_cash_flow": None,
        "book_value_per_share": None,
    }
    # derive EPS if we have P/E and a price
    price = result["close"] or result["ldcp"]
    if pe and price and pe != 0:
        result["eps_ttm"] = round(price / pe, 4)
    else:
        result["eps_ttm"] = None

    # market cap (in '000 PKR): use scraped value, else compute shares x price
    if not result["market_cap_000"] and shares and price:
        result["market_cap_000"] = round(shares * price / 1000.0, 0)

    cache.set(key, result)
    return result


# --------------------------------------------------------------------------- #
# Historical daily prices
# --------------------------------------------------------------------------- #
def get_history(symbol: str, ttl=43200):
    """Daily EOD history -> list of {date_epoch, close, volume, prev_close} oldest->newest."""
    symbol = symbol.upper()
    key = f"history:{symbol}"
    hit = cache.get(key, ttl)
    if hit is not None:
        return hit
    try:
        raw = json.loads(_fetch(f"/timeseries/eod/{symbol}"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return []
    rows = raw.get("data", []) if isinstance(raw, dict) else []
    out = []
    for r in rows:
        if len(r) >= 3:
            out.append(
                {
                    "t": int(r[0]),
                    "close": float(r[1]),
                    "volume": float(r[2]),
                    "prev_close": float(r[3]) if len(r) > 3 else None,
                }
            )
    out.sort(key=lambda x: x["t"])  # oldest first
    cache.set(key, out)
    return out


# --------------------------------------------------------------------------- #
# Parallel helpers
# --------------------------------------------------------------------------- #
def fetch_many(symbols, func, max_workers=8):
    """Run a per-symbol fetch function across many symbols concurrently."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(func, s): s for s in symbols}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                results[sym] = fut.result()
            except Exception:
                results[sym] = None
    return results
