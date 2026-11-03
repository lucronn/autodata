-- Disposable fixture only. The harness binds the module path using psql's
-- SQL-literal variable syntax; it is never applied to an existing server.
CREATE ROLE autodata_schema_probe LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE autodata_metrics LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE autodata_schema_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE autodata FROM PUBLIC;
GRANT CONNECT ON DATABASE autodata TO autodata_schema_probe, autodata_metrics;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO autodata_schema_probe, autodata_metrics, autodata_schema_owner;
CREATE FUNCTION public.probe_heap(internal) RETURNS table_am_handler
 AS :'sentinel_module', 'probe_heap' LANGUAGE C STRICT;
CREATE FUNCTION public.probe_btree(internal) RETURNS index_am_handler
 AS :'sentinel_module', 'probe_btree' LANGUAGE C STRICT;
CREATE FUNCTION public.probe_fdw() RETURNS fdw_handler
 AS :'sentinel_module', 'probe_fdw' LANGUAGE C STRICT;
CREATE FUNCTION public.probe_text(text) RETURNS text
 AS :'sentinel_module', 'probe_text' LANGUAGE C STRICT IMMUTABLE;
CREATE FUNCTION public.probe_predicate(text) RETURNS boolean
 AS :'sentinel_module', 'probe_predicate' LANGUAGE C STRICT IMMUTABLE;
CREATE FUNCTION public.probe_cmp(text,text) RETURNS integer
 AS :'sentinel_module', 'probe_cmp' LANGUAGE C STRICT IMMUTABLE;
CREATE TYPE public.probe_type;
CREATE FUNCTION public.probe_input(cstring) RETURNS public.probe_type
 AS :'sentinel_module', 'probe_input' LANGUAGE C STRICT IMMUTABLE;
CREATE FUNCTION public.probe_output(public.probe_type) RETURNS cstring
 AS :'sentinel_module', 'probe_output' LANGUAGE C STRICT IMMUTABLE;
CREATE TYPE public.probe_type (INPUT=public.probe_input, OUTPUT=public.probe_output,
 INTERNALLENGTH=variable, STORAGE=extended, ALIGNMENT=int4);
CREATE ACCESS METHOD probe_heap TYPE TABLE HANDLER public.probe_heap;
CREATE ACCESS METHOD probe_btree TYPE INDEX HANDLER public.probe_btree;
CREATE OPERATOR CLASS public.probe_btree_text_ops DEFAULT FOR TYPE text USING probe_btree AS
 OPERATOR 1 pg_catalog.<(text,text), OPERATOR 2 pg_catalog.<=(text,text),
 OPERATOR 3 pg_catalog.=(text,text), OPERATOR 4 pg_catalog.>=(text,text),
 OPERATOR 5 pg_catalog.>(text,text), FUNCTION 1 pg_catalog.bttextcmp(text,text);
CREATE OPERATOR CLASS public.probe_text_ops FOR TYPE text USING btree AS
 OPERATOR 1 pg_catalog.<(text,text), OPERATOR 2 pg_catalog.<=(text,text),
 OPERATOR 3 pg_catalog.=(text,text), OPERATOR 4 pg_catalog.>=(text,text),
 OPERATOR 5 pg_catalog.>(text,text), FUNCTION 1 public.probe_cmp(text,text);
CREATE FOREIGN DATA WRAPPER probe_fdw HANDLER public.probe_fdw;
CREATE SERVER probe_server FOREIGN DATA WRAPPER probe_fdw;
CREATE TABLE public.other_table (value text);
CREATE TABLE public.schema_migrations(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE public.schema_migrations OWNER TO autodata_schema_owner;
GRANT SELECT, MAINTAIN ON public.schema_migrations TO autodata_schema_probe;
GRANT SELECT ON public.schema_migrations TO autodata_metrics;
INSERT INTO public.schema_migrations(version) VALUES ('001_initial'),('002_accounts');
