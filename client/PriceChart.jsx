import React, { useEffect, useRef } from "react";

// Simple moving average series (nulls until the window fills) — same as app.js.
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

// Canvas line chart (price + 50/200-day MAs), no charting library — ported from
// the original drawChart() so it renders identically.
export default function PriceChart({ hist }) {
  const ref = useRef(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv || !hist || !hist.points || !hist.points.length) return;
    const pts = hist.points;
    const closes = pts.map((p) => p.close);
    const ma50 = smaSeries(closes, 50);
    const ma200 = smaSeries(closes, 200);

    const dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth || 600;
    const H = 240;
    cv.width = W * dpr;
    cv.height = H * dpr;
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const padL = 46, padR = 10, padT = 12, padB = 22;
    const vals = closes.concat(
      ma50.filter((x) => x != null),
      ma200.filter((x) => x != null)
    );
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.08 || 1;
    lo -= pad;
    hi += pad;
    const x = (i) => padL + (i / (closes.length - 1)) * (W - padL - padR);
    const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);

    ctx.strokeStyle = "#eef1f6";
    ctx.fillStyle = "#9aa6b8";
    ctx.font = "11px Segoe UI";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let g = 0; g <= 4; g++) {
      const v = lo + (hi - lo) * (g / 4);
      const yy = y(v);
      ctx.beginPath();
      ctx.moveTo(padL, yy);
      ctx.lineTo(W - padR, yy);
      ctx.stroke();
      ctx.fillText(v.toFixed(1), padL - 6, yy);
    }

    const line = (series, color, width) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < series.length; i++) {
        if (series[i] == null) continue;
        const px = x(i), py = y(series[i]);
        if (!started) {
          ctx.moveTo(px, py);
          started = true;
        } else ctx.lineTo(px, py);
      }
      ctx.stroke();
    };
    line(closes, "#1f6feb", 1.6);
    line(ma50, "#138a4e", 1.4);
    line(ma200, "#c4322f", 1.4);
  }, [hist]);

  return (
    <div className="chart-wrap" style={{ marginTop: 14 }}>
      <canvas ref={ref} id="priceChart" />
      <div className="chart-legend">
        <span>
          <i style={{ background: "#1f6feb" }} />
          Price
        </span>
        <span>
          <i style={{ background: "#138a4e" }} />
          50-day avg
        </span>
        <span>
          <i style={{ background: "#c4322f" }} />
          200-day avg
        </span>
      </div>
    </div>
  );
}
