-- ALAM migration 033: prevent concurrent durable runs for the same agent.
--
-- agent_runs is the coordination/health ledger for scheduled content, sync and
-- development agents. Two rows for one agent with status='running' make stale-run
-- recovery and operator health ambiguous and are a strong signal that two workers
-- may be acting on the same ownership lane concurrently. Keep that invariant at the
-- database boundary rather than relying only on scheduler timing.
--
-- This is intentionally a partial unique index: historical completed runs remain
-- unlimited, while at most one unfinished run may exist per non-null agent_id.
-- Existing live state was verified to contain no running rows before rollout.

create unique index if not exists agent_runs_one_running_per_agent_idx
  on public.agent_runs (agent_id)
  where status = 'running';
