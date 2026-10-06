-- Scratch: cost of reading a signed release object's layers (270 scopes, 1,080 artifacts).
DROP TABLE IF EXISTS scratch_objects;
CREATE TABLE scratch_objects (release_name text PRIMARY KEY, content_sha256 text, release_object jsonb);
INSERT INTO scratch_objects
SELECT 'r' || r, md5(r::text) || md5(r::text), jsonb_build_object(
  'schema_version', 'axiom-corpus/release-object/v3',
  'release', 'r' || r,
  'content', jsonb_build_object(
    'scopes', (SELECT jsonb_agg(jsonb_build_object('jurisdiction', 'us-' || (s % 152), 'document_class', 'statute', 'version', '2026-09-' || s || '-scope-with-a-longish-name',
       'provision_rows', 1000 + s, 'navigation_rows', 1000 + s, 'provision_projection_sha256', md5(s::text) || md5(s::text), 'navigation_projection_sha256', md5((s+1)::text) || md5(s::text))) FROM generate_series(1, 270) s),
    'artifacts', (SELECT jsonb_agg(jsonb_build_object('artifact_class', 'provisions', 'path', 'data/corpus/provisions/us/statute/2026-09-' || a || '-scope-with-a-longish-name.jsonl', 'sha256', md5(a::text) || md5(a::text), 'bytes', a * 1000, 'r2_bucket', 'axiom-corpus', 'r2_key', 'objects/sha256/ab/' || md5(a::text) || md5(a::text))) FROM generate_series(1, 1080) a),
    'validation', jsonb_build_object('supabase_projection_evidence', (SELECT jsonb_agg(jsonb_build_object('jurisdiction', 'us-' || e, 'expected', e, 'actual', e, 'expected_provision_projection_sha256', md5(e::text) || md5(e::text), 'actual_provision_projection_sha256', md5(e::text) || md5(e::text))) FROM generate_series(1, 270) e))
  ))
FROM generate_series(1, 3) r;
SELECT pg_column_size(release_object) AS stored_bytes, length(release_object::text) AS text_bytes FROM scratch_objects LIMIT 1;
\timing on
-- 300 schema reads (one per pointer move side of a 152-pair activation)
DO $$ DECLARE v text; n int := 0; BEGIN FOR g IN 1..300 LOOP SELECT release_object ->> 'schema_version' INTO v FROM scratch_objects WHERE release_name = 'r' || (1 + g % 3); n := n + length(v); END LOOP; RAISE NOTICE 'schema reads: %', n; END $$;
-- 300 base-pair containment checks
DO $$ DECLARE v boolean; n int := 0; BEGIN FOR g IN 1..300 LOOP SELECT release_object #> '{content,scopes}' @> '[{"jurisdiction": "us-7", "document_class": "statute", "layer": "base"}]' INTO v FROM scratch_objects WHERE release_name = 'r' || (1 + g % 3); n := n + v::int; END LOOP; RAISE NOTICE 'containment: %', n; END $$;
DO $$ DECLARE v text; n int := 0; BEGIN FOR g IN 1..300 LOOP SELECT release_object ->> 'schema_version' INTO v FROM scratch_objects WHERE release_name = 'r' || (1 + g % 3); n := n + length(v); END LOOP; RAISE NOTICE 'schema reads: %', n; END $$;
DO $$ DECLARE v boolean; n int := 0; BEGIN FOR g IN 1..300 LOOP SELECT release_object #> '{content,scopes}' @> '[{"jurisdiction": "us-7", "document_class": "statute", "layer": "base"}]' INTO v FROM scratch_objects WHERE release_name = 'r' || (1 + g % 3); n := n + v::int; END LOOP; RAISE NOTICE 'containment: %', n; END $$;
DO $$ DECLARE v text; n int := 0; BEGIN FOR g IN 1..300 LOOP SELECT release_object ->> 'schema_version' INTO v FROM scratch_objects WHERE release_name = 'r' || (1 + g % 3); n := n + length(v); END LOOP; RAISE NOTICE 'schema reads: %', n; END $$;
DO $$ DECLARE v boolean; n int := 0; BEGIN FOR g IN 1..300 LOOP SELECT release_object #> '{content,scopes}' @> '[{"jurisdiction": "us-7", "document_class": "statute", "layer": "base"}]' INTO v FROM scratch_objects WHERE release_name = 'r' || (1 + g % 3); n := n + v::int; END LOOP; RAISE NOTICE 'containment: %', n; END $$;
DROP TABLE scratch_objects;
