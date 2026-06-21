"""Technical indicators implemented in pure Python (no numpy/pandas).

Inputs are plain lists of daily closing prices (oldest -> newest). Each function
is defensive: if there is not enough history it returns None instead of crashing.
We only have daily CLOSE history from the free feed, so indicators that strictly
need intraday high/low (true ATR) are approximated from close-to-close moves and
clearly labelled as such in the analysis layer.
"""
from __future__ import annotations

import math


def sma(values, period):
    if not values or len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values, period):
    if not values or len(values) < period:
        return []
    k = 2 / (period + 1)
    # seed with simple average of first `period`
    ema = sum(values[:period]) / period
    out = [ema]
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
        out.append(ema)
    return out


def ema(values, period):
    series = _ema_series(values, period)
    return series[-1] if series else None


def rsi(values, period=14):
    if not values or len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    # Wilder's smoothing
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(values, fast=12, slow=26, signal=9):
    if not values or len(values) < slow + signal:
        return None
    fast_e = _ema_series(values, fast)
    slow_e = _ema_series(values, slow)
    # align tails
    n = min(len(fast_e), len(slow_e))
    macd_line = [fast_e[-n + i] - slow_e[-n + i] for i in range(n)]
    signal_series = _ema_series(macd_line, signal)
    if not signal_series:
        return None
    macd_val = macd_line[-1]
    sig_val = signal_series[-1]
    return {
        "macd": round(macd_val, 4),
        "signal": round(sig_val, 4),
        "histogram": round(macd_val - sig_val, 4),
    }


def bollinger(values, period=20, mult=2.0):
    if not values or len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    var = sum((x - mid) ** 2 for x in window) / period
    sd = math.sqrt(var)
    upper = mid + mult * sd
    lower = mid - mult * sd
    price = values[-1]
    width = (upper - lower) / mid if mid else None
    pct_b = (price - lower) / (upper - lower) if upper != lower else None
    return {
        "upper": round(upper, 2),
        "mid": round(mid, 2),
        "lower": round(lower, 2),
        "width_pct": round(width * 100, 2) if width is not None else None,
        "percent_b": round(pct_b, 3) if pct_b is not None else None,
    }


def atr_proxy(values, period=14):
    """ATR approximation from close-to-close absolute moves (no intraday H/L on free
    feed). Returns an absolute price value; treat as a volatility unit for stops."""
    if not values or len(values) < period + 1:
        return None
    moves = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return round(sum(moves[-period:]) / period, 4)


def realized_vol_pct(values, period=20):
    """Annualised realised volatility (%) from daily log returns."""
    if not values or len(values) < period + 1:
        return None
    rets = []
    for i in range(len(values) - period, len(values)):
        if i <= 0 or values[i - 1] <= 0:
            continue
        rets.append(math.log(values[i] / values[i - 1]))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    daily_sd = math.sqrt(var)
    return round(daily_sd * math.sqrt(252) * 100, 2)


def stochastic(values, period=14, smooth=3):
    """Close-only Stochastic oscillator (%K, %D). We lack intraday H/L on the free
    feed, so highs/lows are taken from closing prices over the window — labelled as
    an approximation in the analysis layer."""
    if not values or len(values) < period + smooth:
        return None
    ks = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        lo, hi = min(window), max(window)
        ks.append(100.0 * (values[i] - lo) / (hi - lo) if hi != lo else 50.0)
    if len(ks) < smooth:
        return None
    d = sum(ks[-smooth:]) / smooth
    return {"k": round(ks[-1], 1), "d": round(d, 1)}


def support_resistance(values, lookback=60):
    """Simple swing support/resistance from recent lows/highs."""
    if not values:
        return {"support": None, "resistance": None}
    window = values[-lookback:] if len(values) > lookback else values
    return {"support": round(min(window), 2), "resistance": round(max(window), 2)}


def relative_volume(volumes, period=20):
    """Latest volume vs its recent average (1.0 == average)."""
    if not volumes or len(volumes) < period + 1:
        return None
    avg = sum(volumes[-period - 1 : -1]) / period
    if avg <= 0:
        return None
    return round(volumes[-1] / avg, 2)
