# Step 2 Supabase SQL migration

Run `migrations/001_transaction_foundation.sql` once in **Supabase Dashboard → SQL Editor → New query → Run**.

The script creates `public.accounts`, `public.transactions`, and `public.import_batches` with database-level owner constraints, indexes, and RLS enabled. It intentionally defines no direct Data API policies: React accesses all private transaction data through authenticated FastAPI endpoints, which scope all queries by Supabase Auth user ID.

The SQL script must run before using Step 2 APIs. No new secrets are needed beyond your already configured `backend/.env` and `frontend/.env` from Step 1.

You can check table creation via Supabase Table Editor. Never upload real bank/customer data to the hackathon prototype.
