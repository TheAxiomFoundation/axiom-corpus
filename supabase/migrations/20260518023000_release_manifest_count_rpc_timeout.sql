-- Allow full-release count snapshots to run past the pooler's default
-- statement timeout. This RPC is service-role only and read-only; callers use
-- it for release validation snapshots where a 68-scope corpus aggregate can
-- legitimately take longer than ordinary app reads.

ALTER FUNCTION corpus.get_release_provision_counts(jsonb)
  SET statement_timeout TO 0;

NOTIFY pgrst, 'reload schema';
