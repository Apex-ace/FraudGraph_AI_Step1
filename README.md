# FraudGraph AI - TECHVERSE 2.0 / Team Innova

**FT-PS-02 · Suspicious Transaction Network Detector**

Team: Anvisha Sorte · Chanchal Kohale · Kalpana Channe · Ayush Mishra

## What Step 1 provides

- React + Vite + Tailwind CSS starter at `http://localhost:5173`
- Python FastAPI running at `http://localhost:8000`
- Supabase Auth email/password login in the frontend
- Backend Supabase access-token verification for protected API endpoints
- SQLAlchemy/psycopg connectivity test for Supabase PostgreSQL
- Authenticated personal Socket.IO channel and a development-only notification test

**Not built yet:** transaction tables, fraud rules, actual risk alerts, alert persistence or graph visualization. The notification is an explicitly labelled synthetic test event.

## Prerequisites

- Node.js 20.19+ or 22.12+ (Node 22 LTS recommended)
- Python 3.11+ (3.12 recommended)
- A Supabase project; do not use real bank customer data

## A. Set up Supabase

1. Create a project at https://supabase.com/dashboard.
2. In Project Settings > API Keys, locate the project URL and publishable key (`sb_publishable_...`). Older projects may provide a legacy anon key; the same frontend env variable can hold that public key.
3. In the Supabase dashboard, go to **Connect** and copy the **Session Pooler** PostgreSQL URI. This option supports IPv4-only machines; use the exact Supabase-provided host and username. The session pooler uses port `5432`.
4. Replace `[YOUR-PASSWORD]` in the connection URI with your DB password, URL-encoding special characters (`@` -> `%40`, `#` -> `%23`, etc). Change the URI prefix `postgresql://` to `postgresql+psycopg://` (or leave it and the backend converts it).
5. In Authentication > Providers ensure Email authentication is enabled. New accounts may require email confirmation, depending on your Supabase Auth settings.

Never paste a database password or a secret/service-role API key into the Vite `.env`.

## B. Backend setup (Windows PowerShell)

Open a terminal in this folder:

```powershell
cd .\backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` with values from **your own** Supabase project. `APP_ENV=development` is required for the demo notification endpoint.

Start FastAPI without changing PowerShell execution policies:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/api/health`; expected output:

```json
{"status":"ok","service":"fraudgraph-api","stage":"step-1"}
```

Optional: API docs at `http://localhost:8000/docs` (the normal FastAPI routes appear inside the Socket.IO ASGI wrapper).

If Python 3.12 is not installed, use any installed Python 3.11+ by replacing `py -3.12` with `py -3.11` or `python`.

## C. Frontend setup (second PowerShell terminal)

From the project root:

```powershell
cd .\frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Edit `frontend/.env` using the same Supabase URL and *publishable* key as the backend. Open `http://localhost:5173`.

## D. Step 1 success checklist

1. `http://localhost:8000/api/health` reports `status: ok`.
2. React loads at `http://localhost:5173` with `API: online`.
3. Create a test user (verify their email if requested), then sign in.
4. Socket.IO status changes to `connected`.
5. Click **Test database** and check it reports `connected`.
6. Click **Send test notification** and see a new DEMO notification in the React interface.

**If the database fails:** Ensure you used Supabase Connect > Session Pooler (`5432`), URL-encoded the password, and configured both `.env` files. See the FastAPI terminal logs (do not share credentials).

**If the socket fails:** Ensure API URL and frontend origin match exactly (`http://localhost:8000` and `http://localhost:5173` respectively). Login must succeed first; arbitrary socket clients are refused.

## Security and scope

- Backend validates Supabase JWT tokens **with Supabase Auth** rather than trusting an unverified JWT payload.
- Socket rooms are controlled by the backend and scoped to the authenticated user ID.
- Database URI is stored only in the backend `.env`, never in the browser.
- No DB records or fraud scores are created in Step 1. The demo notification route runs only when `APP_ENV=development` and is not rate-limited, so do not expose it publicly.
- Do not enable anonymous or unrestricted transaction database access. We will add schema, migrations and Row Level Security in Step 2.
- Keep the dev server local; a production release will require rate limiting, monitoring, tested reverse proxy settings and secure HTTPS.

## Next: Step 2

Define PostgreSQL tables for account, transaction, import batch and user profile; add initial migrations; build validated transaction upload and list APIs using synthetic data.
