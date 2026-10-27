# FraudGraph AI — Step 2A: Professional UI & Live Synthetic Simulator

**TECHVERSE 2.0 · FT-PS-02 · Team Innova**

Members: Anvisha Sorte, Chanchal Kohale, Kalpana Channe, Ayush Mishra

## What this update implements

- Professional **light-themed analyst dashboard** with sidebar navigation, account counts, transaction activity and compact investigation-style UI. No marketing landing-page hero, gradients or animated vanity charts.
- Interactive **Cytoscape.js financial network** based on the user's **persisted PostgreSQL transactions**. Bank, consumer, wallet and merchant nodes have different shapes/colors/icons. Hover a node or connection to see its details; click for a small inspector; search and filter demo paths; fit/zoom/rearrange graph.
- Owner-scoped FastAPI **live synthetic transaction generator**. Click *Start Simulation*: FastAPI seeds 21 demo accounts and, if needed, 24 initial transactions; then commits one new synthetic transfer every 2/3/5/10 seconds. **Each transaction is actually stored in the existing `transactions` table.** Socket.IO sends it only to the authenticated user's room; React refetches the backend network graph and ledger.
- Repeating **controlled scenario patterns**: (a) circular A→B→C→A, (b) rapid A→B→C→D, (c) fan-in / fan-out mule-shaped flow, interleaved with normal transfers. Red lines in the chart indicate deliberately injected synthetic test patterns **NOT confirmed fraud**. Completed scenario sequences appear on the *Scenario Events* page. Real fraud detection and model-based scoring are Step 3.
- Start/Stop/Reset controls with per-user scoping, demo-data-only cleanup, fixed maximum **120 ticks per run**, **1,200 generated rows total per user** and *off-by-default* operation. Stop does not delete transactions. Restarting FastAPI stops all in-process simulations; persisted rows remain.
- Existing Step 1 authenticated Socket.IO and Supabase token validation retained; existing Step 2 account/transaction/import endpoints retained.

## Install into your existing working Step 2 project

**Prerequisite:** You completed Step 2 and executed `database/migrations/001_transaction_foundation.sql` in Supabase. This update does **not** require another SQL migration; it reuses the existing accounts and transactions tables.

1. Stop the running frontend and backend (`Ctrl+C`).
2. Extract `FraudGraph_AI_Step2A_Upgrade.zip` **into `D:\FraudGraph_AI_Step1`**. Overwrite the matching source files. The ZIP does not contain `backend/.env`, `frontend/.env`, or `node_modules`; **keep those existing local files**.

   ```powershell
   Expand-Archive -LiteralPath "$HOME\Downloads\FraudGraph_AI_Step2A_Upgrade.zip" -DestinationPath "D:\FraudGraph_AI_Step1" -Force
   ```

3. Make sure `backend/.env` contains `APP_ENV=development` (the simulator is deliberately disabled in other environments).
4. Start FastAPI:

   ```powershell
   cd D:\FraudGraph_AI_Step1\backend
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

5. Start React (this installs **Cytoscape.js** and **Lucide React**, the new packages):

   ```powershell
   cd D:\FraudGraph_AI_Step1\frontend
   npm install
   npm run dev
   ```

6. Sign in at **http://localhost:5173** using your existing Supabase account.

## Validate the live system

1. Visit **Live Simulator** and click **Start Simulation**. The backend should insert an initial network of **21 synthetic accounts and 24 synthetic transactions** if your account has no prior `FGSIM_` demo data.
2. Visit **Overview** / **Network Explorer**. Nodes and edges come from `/api/monitor/graph`, which queries Supabase PostgreSQL. Node labels contain codes such as `SYN_U01`, `SYN_W01` and `SYN_M01`.
3. Watch a new transaction appear every selected interval. On every authenticated Socket.IO `simulation_transactions` event, the browser refreshes the stored graph and transaction feed. It polls every 20 seconds as a fallback when Socket.IO is disconnected. The chart preserves node positions on updates.
4. After 3 completed simulation ticks, a deliberately injected 3-link circular test scenario should appear. More test scenarios arrive over subsequent ticks.
5. **Stop Simulation** and confirm the record counts no longer increase. **Start** again to resume a new bounded run. **Reset Demo Data** deletes only owner-scoped transactions with the reserved `FGSIM_` prefix. Imported/manual transactions cannot use this reserved namespace after this upgrade. Demo account records intentionally remain because existing ledger rows may reference them.
6. Import the Step 2 sample CSV and verify those transactions remain after a demo reset. Sign in as another user to confirm the dashboard is owner-scoped.

## New protected API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/monitor/graph?limit=400` | Account nodes, transaction edges, synthetic test-scenario summaries, ledger counts |
| GET | `/api/simulation/status` | Status of current user's simulator |
| POST | `/api/simulation/start` | `{ "interval_seconds": 3 }` (2–10 allowed) |
| POST | `/api/simulation/stop` | Stop and await current user's loop |
| POST | `/api/simulation/reset` | `{ "confirm": "RESET_SIMULATION" }` deletes current user's generated transactions |

All endpoints require an actual Supabase Auth bearer token. Start, stop, status and reset are development-only. The simulator **never calls a payment rail, banking API or external transaction service**.

## Design & architecture notes

- The simulator runs as an `asyncio` task inside the **single FastAPI development worker** with SQLAlchemy inserts in a threadpool. This is appropriate for a hackathon prototype, not multi-worker production deployment. Launching multiple workers would require a centralized queue/leader lock and distributed Socket.IO coordination.
- Supabase password, service secret and connection string stay in `backend/.env`, never the frontend. The simulator never stores real names, bank details or credentials.
- The network endpoint operates on the **latest 20–500 transactions** requested by the client (400 by default). Historical rows remain stored but older rows are not plotted. Filtering to "demo patterns only" dims unrelated edges; it does not change ledger data.
- **Important:** Red graph links and Scenario Events are scenario labels derived from the simulator's reserved transaction-ID naming convention. They are not evidence that a real financial account is fraudulent. The next milestone builds graph-algorithm detection based on transaction behavior independent of those labels.
- Native/browser background push notifications are **not** implemented. Socket.IO updates the app while the browser is connected; persistent transaction records survive reconnects.
- Step 2 imports support up to 1,000 CSV rows/2 MiB. The simulator's cap limits demo storage. Start is opt-in only.

## Tests

```powershell
cd D:\FraudGraph_AI_Step1\backend
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q tests\test_ledger.py tests\test_simulator.py
```

In this author's execution environment, **9 backend unit tests passed** using SQLite with foreign keys enabled and a Socket.IO test stub (since external Python package downloads were unavailable). JSX syntax checks passed using the TypeScript parser. Full React Vite build and live Supabase/Socket.IO integration must be run on the user's machine because package registry and Supabase access are unavailable here.
