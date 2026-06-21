// Formatting helpers + tiny presentational atoms, ported 1:1 from the original
// vanilla app.js so the look and the colour logic stay identical.

export function fmt(n, dp = 2) {
  if (n === null || n === undefined || n === "" || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-PK", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
}

export function fmtBig(n) {
  if (n == null || isNaN(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e12) return (n / 1e12).toFixed(2) + " T";
  if (a >= 1e9) return (n / 1e9).toFixed(2) + " bn";
  if (a >= 1e6) return (n / 1e6).toFixed(2) + " mn";
  if (a >= 1e3) return (n / 1e3).toFixed(1) + " k";
  return fmt(n, 0);
}

export function scoreColor(s) {
  if (s == null) return "#9aa6b8";
  if (s >= 70) return "#138a4e";
  if (s >= 55) return "#1f6feb";
  if (s >= 45) return "#b5740c";
  return "#c4322f";
}

export function recClass(rec) {
  return "rec rec-" + (rec || "").toLowerCase().replace(/\s+/g, "-");
}

export function signalColor(s) {
  return (
    {
      green: "var(--green)",
      amber: "var(--amber)",
      red: "var(--red)",
      Bullish: "var(--green)",
      Neutral: "var(--amber)",
      Bearish: "var(--red)",
    }[s] || "var(--muted)"
  );
}

const BADGE_LABEL = {
  actual: "Actual",
  calculated: "Calculated",
  assumption: "Assumption",
  opinion: "Opinion",
  external: "External",
};

export function Badge({ kind }) {
  const k = (kind || "calculated").toLowerCase();
  return <span className={`badge badge-${k}`}>{BADGE_LABEL[k] || k}</span>;
}

export function MoS({ m }) {
  if (m == null) return <span className="muted">—</span>;
  const cls = m >= 0 ? "pos" : "neg";
  const sign = m >= 0 ? "+" : "";
  return (
    <span className={cls}>
      {sign}
      {fmt(m, 1)}%
    </span>
  );
}

export function ScoreBar({ s, w = 60 }) {
  const v = Math.max(0, Math.min(100, s || 0));
  return (
    <span className="score-bar" style={{ width: w ? `${w}px` : undefined }}>
      <i style={{ width: `${v}%`, background: scoreColor(s) }} />
    </span>
  );
}

// Radial score gauge (SVG, no libraries).
export function Gauge({ score, size = 96 }) {
  const v = Math.max(0, Math.min(100, score || 0));
  const r = (size - 14) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - v / 100);
  const col = scoreColor(score);
  const mid = size / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="gauge">
      <circle cx={mid} cy={mid} r={r} fill="none" stroke="#e7ebf2" strokeWidth="9" />
      <circle
        cx={mid}
        cy={mid}
        r={r}
        fill="none"
        stroke={col}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={off}
        transform={`rotate(-90 ${mid} ${mid})`}
      />
      <text x="50%" y="50%" textAnchor="middle" dy="0.05em" className="gauge-num" fill={col}>
        {fmt(score, 0)}
      </text>
      <text x="50%" y="50%" textAnchor="middle" dy="1.5em" className="gauge-sub">
        /100
      </text>
    </svg>
  );
}

export function Kpi({ label, val, sub }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-val">{val}</div>
      {sub ? <div className="kpi-sub">{sub}</div> : null}
    </div>
  );
}

export function MiniCell({ label, val }) {
  return (
    <div className="setup-cell">
      <div className="sc-label">{label}</div>
      <div className="sc-value">{val}</div>
    </div>
  );
}
