-- Search index over the canonical rulespec-* GitHub repos.
--
-- The encoded-rule search lane used to crawl the GitHub org at query
-- time (org listing + one tree per jurisdiction + one raw fetch per
-- candidate YAML). This table replaces that with a single indexed
-- query: scripts/sync-rulespec-index.mjs crawls the repos on a
-- schedule and upserts one row per encoding file, carrying the raw
-- YAML so the app can score rule symbols locally without any GitHub
-- round-trips.
--
-- search_text is a pre-tokenised bag of words (citation path segments,
-- rule names, formula identifiers, module summary) built by the sync
-- script; search_tsv indexes it for the OR-of-terms candidate query.

create table if not exists encodings.rulespec_files (
  citation_path text primary key,
  file_path     text not null,
  repo          text not null,
  branch        text not null,
  jurisdiction  text not null,
  bucket        text not null,
  raw_yaml      text,
  search_text   text not null default '',
  search_tsv    tsvector generated always as (to_tsvector('simple', search_text)) stored,
  synced_at     timestamptz not null default now()
);

create index if not exists rulespec_files_search_tsv_idx
  on encodings.rulespec_files using gin (search_tsv);
create index if not exists rulespec_files_jurisdiction_idx
  on encodings.rulespec_files (jurisdiction);

alter table encodings.rulespec_files enable row level security;

drop policy if exists "rulespec_files are publicly readable" on encodings.rulespec_files;
create policy "rulespec_files are publicly readable"
  on encodings.rulespec_files for select using (true);

grant select on encodings.rulespec_files to anon, authenticated;
