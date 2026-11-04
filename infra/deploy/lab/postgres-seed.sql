\set ON_ERROR_STOP on
SELECT :'mode' = 'seed' AS do_seed \gset
BEGIN;
\if :do_seed
CREATE TABLE IF NOT EXISTS lab_fixture(run_id uuid PRIMARY KEY, payload text NOT NULL);
INSERT INTO lab_fixture(run_id,payload)
VALUES (:'run_id'::uuid, 'autodata-lab-v1:' || :'run_id') ON CONFLICT DO NOTHING;
\endif
SELECT count(*) = 1 AND bool_and(run_id = :'run_id'::uuid AND payload = 'autodata-lab-v1:' || :'run_id') AS fixture_ok
FROM lab_fixture;
COMMIT;
