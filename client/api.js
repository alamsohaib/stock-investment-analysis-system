// Thin fetch wrapper. All endpoints are same-origin (/api/*) — on Vercel the
// Python serverless functions sit next to the static frontend, and in dev Vite
// proxies /api to the local run.py server.
async function get(path) {
  const r = await fetch(path);
  const data = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

export const apiStatus = () => get("/api/status");
export const apiScan = (top = 20) => get(`/api/scan?top=${top}`);
export const apiSearch = (q) => get(`/api/search?q=${encodeURIComponent(q)}`);
export const apiDeepDive = (sym) => get(`/api/deepdive?symbol=${encodeURIComponent(sym)}`);
export const apiHistory = (sym) => get(`/api/history?symbol=${encodeURIComponent(sym)}`);
