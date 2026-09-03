-- Harden browser-callable ALAM SECURITY DEFINER RPCs against search-path hijacking.
-- Re-applying this migration is safe: ALTER FUNCTION SET is idempotent.

alter function public.alam_lookup_device(uuid)
  set search_path = '';

alter function public.alam_register_device(uuid, text, text, jsonb)
  set search_path = '';

alter function public.alam_log_event(uuid, text, text, text, jsonb)
  set search_path = '';

alter function public.alam_link_current_account(uuid)
  set search_path = '';

alter function public.alam_public_sync_health()
  set search_path = '';
