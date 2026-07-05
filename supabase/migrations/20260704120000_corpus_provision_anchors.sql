-- Provision anchors — a derived, rebuildable leaf-level annotation layer over
-- corpus.provisions.
--
-- Ratified 2026-07-04 (docs/granularity-policy-proposal.md §4, "the annotation
-- layer is a real table that goes to the drafted leaves").
--
-- One row per drafted leaf, keyed by its citation path. corpus.provisions
-- stores structure only at the depth the official source *asserts* (the
-- assertion frontier: paragraph/clause for USLM statutes, the section for
-- eCFR, block/page for manuals). Structure below that frontier — the printed
-- paragraph tree inside a CFR section such as 7 CFR 273.9(d)(6)(iii) — is
-- indentation typography, not identified nodes. Baking a parser's guess about
-- where (d)(6)(iii) ends into uuid5(citation_path) identity would make a
-- heuristic load-bearing for every grounding, claim, and staleness pin. So this
-- layer carries that structure as RE-DERIVABLE ANNOTATION: a wrong span is a
-- re-derivation; a wrong identity is a migration across every consumer.
--
-- Disciplines (enforced here + in axiom_corpus.corpus.anchors and its tests):
--   * DERIVED AND REBUILDABLE from (provisions × extractor_version). A boundary
--     correction is a rebuild plus a parent-hash re-check, never a migration.
--   * BYTE-EQUAL: anchor_text must equal parent.body[char_start:char_end]. The
--     generator verifies this; the check constraint here enforces span sanity.
--   * LABEL-AT-HEAD: the printed label ((d),(6),(iii),(A)) sits at the span
--     head. Enforced by the generator (not expressible as a cheap SQL check
--     without the parent body).
--   * THE LEAF PATH IS THE STABLE KEY. A boundary fix changes offsets, not the
--     key. So citation_path is the PRIMARY KEY — not a surrogate row id.
--     Groundings of record cite (parent_provision_id, citation_path, span),
--     never an anchor-row surrogate.
--
-- Dual consumer, mirroring corpus.provision_references:
--   * Axiom viewer — render a parent provision body with a leaf outline;
--     wrap parent.body[char_start:char_end] for a leaf without reparsing.
--   * RuleSpec tooling — resolve a subsection citation path
--     (regulations/7-cfr/273/9/d/6/iii) to (provision_id, span) so a module
--     that grounds on the section can point precisely at its subsection text.
--
-- The table is rebuilt as a batch by the generator, which owns the lifecycle;
-- the loader upserts on the citation_path primary key.

CREATE TABLE IF NOT EXISTS corpus.provision_anchors (
  -- THE STABLE KEY. The leaf's citation path, e.g.
  -- 'us/regulation/7/273/9/d/6/iii' or 'us-ma/regulation/106-cmr/365/180/A'.
  -- Paths are printed labels; a boundary fix moves offsets, never this key.
  citation_path         TEXT PRIMARY KEY,

  -- The ASSERTED provision this leaf lives inside (the corpus row whose body
  -- the span indexes into). Groundings cite this id + the path + the span.
  parent_provision_id   UUID NOT NULL REFERENCES corpus.provisions(id) ON DELETE CASCADE,

  -- Denormalized parent path for human-legible joins / debugging. Equal to the
  -- parent provision's citation_path.
  parent_citation_path  TEXT NOT NULL,

  -- Char offsets into corpus.provisions.body for parent_provision_id. Half-open
  -- [char_start, char_end). These are code-point indices; corpus bodies are
  -- ASCII regulatory text so they coincide with byte offsets.
  char_start            INTEGER NOT NULL CHECK (char_start >= 0),
  char_end              INTEGER NOT NULL CHECK (char_end > char_start),

  -- The leaf's text, MATERIALIZED AS A VERIFIED-DERIVED COLUMN so leaf-level
  -- queries, encoder prompt slicing, and leaf FTS need no second source of
  -- truth. Contract (generator-enforced): byte-equal to
  -- parent.body[char_start:char_end].
  anchor_text           TEXT NOT NULL,

  -- The printed label at the span head, without parens: 'd', '6', 'iii', 'A'.
  label                 TEXT NOT NULL,

  -- 0-based outline depth of this leaf within the parent provision.
  depth                 INTEGER NOT NULL CHECK (depth >= 0),

  -- machine_asserted — the span is a pass-through of a boundary the publisher
  --   already asserts (a stored deeper provision, or a block leaf the source
  --   segmented). The boundary is the publisher's.
  -- label_inferred — the extractor inferred the span from printed-label
  --   typography (the CFR paragraph tree). The boundary is the parser's.
  confidence            TEXT NOT NULL DEFAULT 'label_inferred'
                          CHECK (confidence IN ('machine_asserted', 'label_inferred')),

  -- Soft lifecycle flag; anchors are rebuilt wholesale, but a superseded leaf
  -- can be marked inactive without deleting history.
  status                TEXT NOT NULL DEFAULT 'active',

  -- Extraction provenance. The (parent provision, extractor_version) pair is
  -- the rebuild cache key; bump the version whenever offsets could move.
  extractor_version     TEXT NOT NULL,

  -- sha256 of the parent body at generation time. A parent edit changes this
  -- hash; the loader/verifier treats a mismatch as "rebuild required", so a
  -- silent upstream typography change can't leave stale spans trusted.
  parent_body_sha256    TEXT NOT NULL DEFAULT '',

  -- Denormalized release scope (match corpus.provisions columns) so anchors can
  -- be filtered to the same version boundary as their parents.
  jurisdiction          TEXT,
  document_class        TEXT,
  version               TEXT,

  -- Sibling display order within the parent provision.
  ordinal               INTEGER,

  -- Free-form jsonb for extractor notes (e.g. source rule cross-reference).
  metadata              JSONB,

  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "What leaves does THIS provision have?" — the viewer's leaf-outline query and
-- the resolver's descendant/ancestor walk both start here.
CREATE INDEX IF NOT EXISTS idx_provision_anchors_parent
  ON corpus.provision_anchors (parent_provision_id);

CREATE INDEX IF NOT EXISTS idx_provision_anchors_parent_path
  ON corpus.provision_anchors (parent_citation_path);

-- Prefix search for descendant resolution ("all leaves under .../273/9/d").
CREATE INDEX IF NOT EXISTS idx_provision_anchors_path_pattern
  ON corpus.provision_anchors (citation_path text_pattern_ops);

-- Filter to a release boundary alongside corpus.current_provisions.
CREATE INDEX IF NOT EXISTS idx_provision_anchors_scope
  ON corpus.provision_anchors (jurisdiction, document_class, version);

CREATE INDEX IF NOT EXISTS idx_provision_anchors_confidence
  ON corpus.provision_anchors (confidence);


-- ======================================================================
-- RPC: resolve_provision_anchor(citation_path)
-- ======================================================================
-- Server-side mirror of axiom_corpus.corpus.anchors.AnchorResolver. Returns at
-- most one row: an exact leaf if present, else the minimal span covering all
-- descendant leaves (when they share one parent provision), else the deepest
-- stored ancestor leaf. Match kind is reported so callers know the fallback
-- that fired. Nothing matched → zero rows.

CREATE OR REPLACE FUNCTION corpus.resolve_provision_anchor(citation_path_in text)
RETURNS TABLE (
  match_kind            text,     -- 'exact' | 'descendant' | 'ancestor'
  citation_path         text,
  parent_provision_id   uuid,
  parent_citation_path  text,
  char_start            integer,
  char_end              integer,
  anchor_text           text,
  confidence            text
)
LANGUAGE sql
STABLE
AS $$
  -- exact
  SELECT
    'exact'::text,
    a.citation_path,
    a.parent_provision_id,
    a.parent_citation_path,
    a.char_start,
    a.char_end,
    a.anchor_text,
    a.confidence
  FROM corpus.provision_anchors a
  WHERE a.citation_path = citation_path_in

  UNION ALL

  -- descendant: query is an ancestor of drafted leaves that share ONE parent
  -- provision. One aggregated row; the HAVING guard fires it only when there is
  -- at least one descendant and they all live in a single parent provision
  -- (so MIN(parent_*) is that unique parent). No GROUP BY, so COUNT(DISTINCT …)
  -- is a plain aggregate — not a window function.
  SELECT
    'descendant'::text,
    citation_path_in,
    -- Guarded to a single distinct parent, so MIN(...::text) is that parent.
    MIN(d.parent_provision_id::text)::uuid,
    MIN(d.parent_citation_path),
    MIN(d.char_start)::int,
    MAX(d.char_end)::int,
    NULL::text,
    NULL::text
  FROM corpus.provision_anchors d
  WHERE d.citation_path LIKE citation_path_in || '/%'
    AND NOT EXISTS (
      SELECT 1 FROM corpus.provision_anchors e
      WHERE e.citation_path = citation_path_in
    )
  HAVING COUNT(*) > 0
     AND COUNT(DISTINCT d.parent_provision_id) = 1

  UNION ALL

  -- ancestor: deepest stored prefix of the query. Wrapped in a subquery so its
  -- ORDER BY / LIMIT is scoped to this branch (a top-level ORDER BY on a
  -- UNION cannot reference a branch's table alias).
  SELECT * FROM (
    SELECT
      'ancestor'::text,
      a.citation_path,
      a.parent_provision_id,
      a.parent_citation_path,
      a.char_start,
      a.char_end,
      a.anchor_text,
      a.confidence
    FROM corpus.provision_anchors a
    WHERE citation_path_in LIKE a.citation_path || '/%'
      AND NOT EXISTS (
        SELECT 1 FROM corpus.provision_anchors e
        WHERE e.citation_path = citation_path_in
      )
      AND NOT EXISTS (
        SELECT 1 FROM corpus.provision_anchors d
        WHERE d.citation_path LIKE citation_path_in || '/%'
      )
    ORDER BY length(a.citation_path) DESC
    LIMIT 1
  ) ancestor_match;
$$;

GRANT EXECUTE ON FUNCTION corpus.resolve_provision_anchor(text) TO anon;
GRANT EXECUTE ON FUNCTION corpus.resolve_provision_anchor(text) TO authenticated;


-- ======================================================================
-- Grants + RLS (matches corpus.provisions / corpus.provision_references;
-- Supabase defaults don't cover new tables)
-- ======================================================================

GRANT ALL ON TABLE corpus.provision_anchors TO postgres, service_role;
GRANT SELECT ON TABLE corpus.provision_anchors TO anon, authenticated;

ALTER TABLE corpus.provision_anchors ENABLE ROW LEVEL SECURITY;

CREATE POLICY anon_read ON corpus.provision_anchors
  FOR SELECT TO anon USING (true);
CREATE POLICY authenticated_read ON corpus.provision_anchors
  FOR SELECT TO authenticated USING (true);

NOTIFY pgrst, 'reload schema';
