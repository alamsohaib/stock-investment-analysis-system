# Deploying PSX Analyst to Vercel (React frontend + Python serverless API)

This repo now has **two ways to run**:

| | What runs | Use it for |
|---|---|---|
| **Desktop app** | `python run.py` → local `http.server` | Full power: 120-stock background scan, persistent disk cache. |
| **Hosted app** | React frontend + Python serverless functions on **Vercel** | A public URL anyone can open. |

The hosted version is a faithful **React cover** over the same analysis engine — but
serverless hosting imposes two honest limits (see *Caveats* below).

---

## What was added

```
index.html            ← Vite entry (loads /client/main.jsx)
vite.config.js         ← build + local /api proxy
package.json           ← React/Vite deps
client/                ← the React app (App, DeepDive, PriceChart, format, api)
api/                   ← Vercel Python serverless functions
  status.py  scan.py  deepdive.py  history.py  search.py
  _lib/                ← a copy of src/ (the analysis engine), imported by the functions
vercel.json            ← maxDuration + bundles api/_lib with each function
requirements.txt       ← empty (stdlib only); signals the Python runtime to Vercel
```

Your original `src/`, `web/`, `run.py` are untouched — the desktop app still works.

---

## Deploy

You need a free [Vercel](https://vercel.com) account.

### Option A — Git (recommended)
1. Push this folder to a GitHub/GitLab repo.
2. In Vercel: **Add New → Project → Import** the repo.
3. Vercel auto-detects **Vite** (build `npm run build`, output `dist`) and deploys
   `api/*.py` as Python functions. Click **Deploy**. Done.

### Option B — CLI
```bash
npm i -g vercel
vercel          # preview deploy
vercel --prod   # production deploy
```

No environment variables are required.

---

## Local development

Run the real backend and the React dev server side by side:

```bash
# terminal 1 — the Python API (same one the desktop app uses)
python run.py            # serves the API on http://127.0.0.1:8800

# terminal 2 — the React UI with hot reload
npm install
npm run dev              # http://localhost:5173  (/api is proxied to :8800)
```

To instead test the **serverless** functions locally exactly as Vercel runs them:
```bash
vercel dev               # runs api/*.py as functions + the Vite frontend
```

---

## Caveats (the honest part)

Serverless functions are stateless and time-limited, so the hosted app differs from
the desktop app on purpose — and the UI says so in a banner:

1. **"Run Analysis" is a *lite scan*.** It synchronously analyses only the
   **12 most-liquid** stocks (a 5-stock scan measured ~8s; 12 stays well under the
   60s Hobby limit) instead of the desktop app's 120-stock background scan. Change the
   count with the **`PSX_LITE_MAX`** env var in Vercel (raise it only if your plan
   allows longer function durations — Pro allows up to 300s).
2. **Caching is best-effort.** The disk cache lives in `/tmp`, which is wiped between
   cold starts, so most requests re-fetch from PSX. The in-memory cache only helps
   within a single warm invocation. (`PSX_CACHE_DIR` can point it elsewhere.)
3. **Outbound scraping from a datacenter.** The functions fetch
   `dps.psx.com.pk` and `stockanalysis.com` from Vercel's US region. If PSX ever
   rate-limits or blocks datacenter IPs, the desktop app (running from your own
   connection) is the reliable fallback.

**Single-stock deep-dives (search any symbol) are fully complete on the hosted app** —
they're one symbol, so they finish in a few seconds and use the entire analysis engine.

> Still just an educational research tool, using free/delayed data. Not financial advice.
