-- The sync workflow upserts via PostgREST with the service_role key;
-- the table was created by the migration admin role, and the encodings
-- schema's default privileges do not extend writes to service_role.
grant usage on schema encodings to service_role;
grant select, insert, update, delete on encodings.rulespec_files to service_role;
