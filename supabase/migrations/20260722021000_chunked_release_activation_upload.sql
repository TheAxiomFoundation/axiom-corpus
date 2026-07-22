-- Stage large signed release objects in bounded management-plane requests.
-- The table is private to postgres; the staging service role cannot use it.
-- The trusted activation caller verifies Ed25519 before uploading canonical
-- JSON chunks, and the loader recomputes the complete object hash before the
-- existing atomic activation function receives the reconstructed object.

CREATE TABLE IF NOT EXISTS corpus.release_activation_upload_chunks (
  upload_id text NOT NULL CHECK (upload_id ~ '^[0-9a-f]{64}$'),
  release_name text NOT NULL CHECK (
    release_name <> 'current'
    AND char_length(release_name) <= 128
    AND release_name ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
  ),
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  chunk_index integer NOT NULL CHECK (chunk_index >= 0),
  chunk_count integer NOT NULL CHECK (chunk_count > 0),
  chunk_text text NOT NULL CHECK (octet_length(chunk_text) <= 131072),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (upload_id, chunk_index),
  CHECK (chunk_index < chunk_count)
);

CREATE INDEX IF NOT EXISTS idx_release_activation_upload_chunks_created_at
  ON corpus.release_activation_upload_chunks (created_at);

ALTER TABLE corpus.release_activation_upload_chunks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON corpus.release_activation_upload_chunks
  FROM anon, authenticated, service_role, PUBLIC;

CREATE OR REPLACE FUNCTION corpus.load_release_activation_upload(
  p_upload_id text,
  p_release_name text,
  p_content_sha256 text,
  p_object_sha256 text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = corpus, public
AS $$
DECLARE
  v_chunk_rows integer;
  v_min_chunk_index integer;
  v_max_chunk_index integer;
  v_min_chunk_count integer;
  v_max_chunk_count integer;
  v_raw text;
  v_object jsonb;
BEGIN
  IF p_upload_id IS NULL OR p_upload_id !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid release activation upload id';
  END IF;
  IF p_release_name IS NULL
     OR p_release_name = 'current'
     OR char_length(p_release_name) > 128
     OR p_release_name !~ '^[a-z0-9]+(-[a-z0-9]+)*$' THEN
    RAISE EXCEPTION 'invalid immutable corpus release name: %', p_release_name;
  END IF;
  IF p_content_sha256 IS NULL OR p_content_sha256 !~ '^[0-9a-f]{64}$'
     OR p_object_sha256 IS NULL OR p_object_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid release activation digest';
  END IF;

  SELECT
    COUNT(*)::integer,
    MIN(chunk_index),
    MAX(chunk_index),
    MIN(chunk_count),
    MAX(chunk_count),
    string_agg(chunk_text, '' ORDER BY chunk_index)
  INTO
    v_chunk_rows,
    v_min_chunk_index,
    v_max_chunk_index,
    v_min_chunk_count,
    v_max_chunk_count,
    v_raw
  FROM corpus.release_activation_upload_chunks
  WHERE upload_id = p_upload_id
    AND release_name = p_release_name
    AND content_sha256 = p_content_sha256;

  IF v_chunk_rows IS NULL
     OR v_chunk_rows = 0
     OR v_min_chunk_count IS DISTINCT FROM v_max_chunk_count
     OR v_chunk_rows IS DISTINCT FROM v_max_chunk_count
     OR v_min_chunk_index IS DISTINCT FROM 0
     OR v_max_chunk_index IS DISTINCT FROM v_chunk_rows - 1 THEN
    RAISE EXCEPTION 'release activation upload is incomplete';
  END IF;
  IF encode(sha256(convert_to(v_raw, 'UTF8')), 'hex') IS DISTINCT FROM p_object_sha256 THEN
    RAISE EXCEPTION 'release activation upload object digest mismatch';
  END IF;

  BEGIN
    v_object := v_raw::jsonb;
  EXCEPTION WHEN invalid_text_representation THEN
    RAISE EXCEPTION 'release activation upload is not valid JSON';
  END;
  IF v_object ->> 'release' IS DISTINCT FROM p_release_name
     OR v_object ->> 'content_sha256' IS DISTINCT FROM p_content_sha256 THEN
    RAISE EXCEPTION 'release activation upload identity mismatch';
  END IF;
  RETURN v_object;
END;
$$;

GRANT EXECUTE ON FUNCTION corpus.load_release_activation_upload(text, text, text, text)
  TO postgres;
REVOKE EXECUTE ON FUNCTION corpus.load_release_activation_upload(text, text, text, text)
  FROM anon, authenticated, service_role, PUBLIC;

NOTIFY pgrst, 'reload schema';
