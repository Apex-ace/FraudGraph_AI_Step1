-- Team Innova · FT-PS-02 · Step 2
-- Paste this entire script into Supabase Dashboard > SQL Editor and run ONCE.
-- Only synthetic transaction data should be stored. No bank credentials or card details.
-- Database connection via the backend has elevated privileges: EVERY API query must
-- filter owner_id using the VERIFIED Supabase Auth user; RLS protects direct Data API access.

create table if not exists public.accounts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  account_code varchar(40) not null,
  label varchar(100),
  created_at timestamptz not null default now(),
  constraint uq_accounts_owner_code unique (owner_id, account_code),
  constraint uq_accounts_owner_id unique (owner_id, id)
);
create index if not exists idx_accounts_owner_created on public.accounts (owner_id, created_at);

create table if not exists public.import_batches (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  file_name varchar(160) not null,
  total_rows integer not null,
  imported_rows integer not null,
  duplicate_rows integer not null,
  created_at timestamptz not null default now(),
  constraint ck_import_counts check (total_rows >= 0 and imported_rows >= 0 and duplicate_rows >= 0),
  constraint uq_import_batches_owner_id unique (owner_id, id)
);
create index if not exists idx_import_batches_owner_created on public.import_batches (owner_id, created_at);

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  transaction_id varchar(64) not null,
  sender_account_id uuid not null,
  receiver_account_id uuid not null,
  amount numeric(18,2) not null,
  currency varchar(3) not null default 'INR',
  occurred_at timestamptz not null,
  status varchar(16) not null default 'completed',
  import_batch_id uuid,
  created_at timestamptz not null default now(),
  constraint uq_transactions_owner_ref unique (owner_id, transaction_id),
  constraint ck_transactions_positive_amount check (amount > 0),
  constraint ck_transactions_distinct_accounts check (sender_account_id <> receiver_account_id),
  constraint ck_transactions_status check (status in ('completed', 'pending', 'failed')),
  constraint fk_transactions_sender foreign key (owner_id, sender_account_id) references public.accounts (owner_id, id),
  constraint fk_transactions_receiver foreign key (owner_id, receiver_account_id) references public.accounts (owner_id, id),
  constraint fk_transactions_batch foreign key (owner_id, import_batch_id) references public.import_batches (owner_id, id)
);
create index if not exists idx_transactions_owner_occurred on public.transactions (owner_id, occurred_at desc);
create index if not exists idx_transactions_sender on public.transactions (owner_id, sender_account_id);
create index if not exists idx_transactions_receiver on public.transactions (owner_id, receiver_account_id);

alter table public.accounts enable row level security;
alter table public.import_batches enable row level security;
alter table public.transactions enable row level security;

-- These tables are intentionally private to FastAPI. We create no anonymous or
-- authenticated Data API policies, so direct frontend SELECT/INSERT is denied.
-- Backend connects using DATABASE_URL and enforces owner_id on ALL reads/writes.
-- Never expose DATABASE_URL or PostgreSQL credentials to the browser.
