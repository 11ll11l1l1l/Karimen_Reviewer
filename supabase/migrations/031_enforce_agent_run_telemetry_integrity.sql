-- ALAM migration 031: enforce durable agent-run lifecycle/count integrity.
--
-- agent_runs coordinates content/development agent health and stale-run detection.
-- Keep its telemetry internally consistent at the database boundary so a buggy or
-- partially updated worker cannot leave impossible completed/running states behind.
-- Existing live rows were verified clean before this migration.

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.agent_runs'::regclass
      and conname = 'agent_runs_nonnegative_counts_check'
  ) then
    alter table public.agent_runs
      add constraint agent_runs_nonnegative_counts_check
      check (
        stories_found >= 0
        and stories_published >= 0
        and stories_rejected >= 0
      );
  end if;

  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.agent_runs'::regclass
      and conname = 'agent_runs_time_order_check'
  ) then
    alter table public.agent_runs
      add constraint agent_runs_time_order_check
      check (finished_at is null or finished_at >= started_at);
  end if;

  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.agent_runs'::regclass
      and conname = 'agent_runs_lifecycle_check'
  ) then
    alter table public.agent_runs
      add constraint agent_runs_lifecycle_check
      check (
        (status = 'running' and finished_at is null)
        or
        (status in ('success', 'partial', 'failed') and finished_at is not null)
      );
  end if;
end
$$;
