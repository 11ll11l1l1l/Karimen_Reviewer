-- ALAM.ph comment contract + daily wisdom compatibility.
-- Safe after 001/002. Keeps agent-generated stable string IDs intact.

alter table public.agent_comments alter column id drop default;
alter table public.agent_comments alter column id type text using id::text;
alter table public.agent_comments add column if not exists persona_id text;
alter table public.agent_comments add column if not exists reply_to text;
alter table public.agent_comments add column if not exists record jsonb not null default '{}'::jsonb;

-- `agent_id` stores the owning/commenting ALAM lens: discover/reflection/practical/trend.
-- `persona_id` stores Kiko/Mara/etc. Existing rows remain valid.

create table if not exists public.wisdom_entries (
  entry_date date primary key,
  based_on text,
  question text not null,
  verses jsonb not null default '[]'::jsonb,
  record jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.wisdom_entries enable row level security;
drop policy if exists "Public can read wisdom" on public.wisdom_entries;
create policy "Public can read wisdom" on public.wisdom_entries for select using (true);
