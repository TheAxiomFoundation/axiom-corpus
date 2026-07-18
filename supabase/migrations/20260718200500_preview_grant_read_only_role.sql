-- The Supabase Management API executes read_only queries as
-- supabase_read_only_user, not postgres, so the read-only activation preview
-- (scripts/activate_release.py --dry-run) needs EXECUTE for that role.
-- Safe: the function is STABLE (cannot write) and SECURITY DEFINER, and the
-- role is the platform's own read-only management role.
GRANT EXECUTE ON FUNCTION corpus.preview_corpus_release_activation(jsonb)
  TO supabase_read_only_user;
