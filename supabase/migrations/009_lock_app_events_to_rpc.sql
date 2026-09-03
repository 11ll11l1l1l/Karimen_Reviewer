-- ALAM.ph telemetry write-boundary hardening.
-- Browser clients must log interaction telemetry only through the validated
-- public.alam_log_event(...) SECURITY DEFINER RPC created by migration 006.
-- This migration is intentionally idempotent and does not modify existing events.

revoke insert on table public.app_events from anon, authenticated;
revoke usage, select on sequence public.app_events_id_seq from anon, authenticated;

drop policy if exists "Anon inserts anonymous app events" on public.app_events;
drop policy if exists "Users insert own app events" on public.app_events;

-- Keep authenticated read access to a user's own historical events unchanged.
-- Keep EXECUTE on public.alam_log_event(uuid,text,text,text,jsonb) unchanged;
-- the function owner retains the privileges needed to insert and use the sequence.
