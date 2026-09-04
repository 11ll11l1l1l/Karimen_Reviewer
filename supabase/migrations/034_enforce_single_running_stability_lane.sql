-- Prevent the stability/integration development lane from bypassing the
-- single-running-agent guard through its historical agent_id alias.
--
-- Keep completed history untouched and retain the existing per-agent index.
-- The constant-expression partial unique index allows at most one live row
-- across the two verified identifiers for this same logical ownership lane.
CREATE UNIQUE INDEX IF NOT EXISTS agent_runs_one_running_stability_lane_idx
ON public.agent_runs ((1))
WHERE status = 'running'
  AND agent_id IN ('stability_integration', 'stability_integration_agent');
