from pathlib import Path
import ast
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from workshop_paid_access_smoke import GO_NAMES, CASE_IDS, CASE_ASSERTIONS, MIGRATION_ASSERTIONS, junit_valid, go_valid, success
import release_acceptance

class PaidAccessCollectorTests(unittest.TestCase):
    def test_exact_twelve_junit_cases_without_skip_failure_or_duplicates(self):
        def xml(extra='',child=''):
            return '<testsuite>'+''.join(f'<testcase classname="tests.test_paid_catalog_api_integration" name="test_required_paid_catalog_access[{case}]">{child if i==0 else ""}</testcase>' for i,case in enumerate(CASE_IDS))+extra+'</testsuite>'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'junit.xml';path.write_text(xml());self.assertTrue(junit_valid(path))
            for content in (xml(child='<skipped/>'),xml(child='<failure/>'),xml(child='<error/>'),xml(extra='<testcase name="other"/>'),'<testsuite/>'):
                path.write_text(content);self.assertFalse(junit_valid(path))
    def test_go_requires_one_root_and_package_pass_with_no_extra_ids(self):
        name=GO_NAMES[0]
        events=[{'Action':'run','Test':name},{'Action':'pass','Test':name},{'Action':'pass'}]
        self.assertTrue(go_valid(events,name))
        for extra in ({'Action':'skip','Test':'Other'},{'Action':'fail'},{'Action':'run','Test':name+'/nested'},{'Action':'pass','Test':'Other'}):self.assertFalse(go_valid(events+[extra],name))
        self.assertFalse(go_valid(events[1:],name))
    def test_missing_case_flag_nonzero_and_timeout_fail_closed(self):
        flags={case:True for case in CASE_IDS}
        self.assertTrue(success(0,False,flags))
        self.assertFalse(success(1,False,flags));self.assertFalse(success(0,True,flags))
        del flags[CASE_IDS[0]];self.assertFalse(success(0,False,flags))
        self.assertEqual(len(CASE_ASSERTIONS),6)

    def test_content_search_checks_are_in_exact_paid_fixture_inventory(self):
        self.assertIn('source_content_search_current_projection',
            CASE_ASSERTIONS[GO_NAMES[2]])
        self.assertIn('canonical_content_search_current_projection',
            CASE_ASSERTIONS[GO_NAMES[2]])
        self.assertIn('content_search_before_rights_change',
            CASE_ASSERTIONS[GO_NAMES[4]])
        self.assertEqual(GO_NAMES, release_acceptance.PAID_GO_ROOTS)
        self.assertEqual(tuple(CASE_ASSERTIONS[name] for name in GO_NAMES),
            release_acceptance.PAID_CASE_ASSERTIONS)

    def test_paid_current_head_migration_contract_uses_actual_source_inventory(self):
        root = Path(__file__).resolve().parents[2]
        manifest = tuple(path.name for path in sorted((root / 'db/migrations').glob('*.sql')))
        self.assertEqual(len(manifest), 42)
        self.assertEqual(manifest[-1], '042_catalog_selector_rows.sql')
        self.assertEqual(release_acceptance.PAID_MIGRATION_MANIFEST, manifest)
        rows = {table: [] for table in release_acceptance.PAID_PG_TABLES}
        rows['schema_migrations'] = [
            dict(version=name[:-4], applied_at='2026-11-16T00:00:00Z')
            for name in manifest]
        release_acceptance._paid_migration_rows(rows)
        expected = ('fresh_manifest_applied_001_042', 'empty_replay_noop_001_042',
                    'populated_replay_noop_001_042')
        self.assertEqual(MIGRATION_ASSERTIONS, expected)
        self.assertEqual(release_acceptance.PAID_MIGRATION_ASSERTIONS, expected)

    def test_actual_paid_child_manifest_guard_accepts_current_head_and_rejects_drift(self):
        # Compile only the owning assertion: never import fixture/DB runtime code.
        root = Path(__file__).resolve().parents[2]
        path = root / 'workers/ingestion-python/tests/test_paid_catalog_api_integration.py'
        child = next(node for node in ast.parse(path.read_text()).body
                     if isinstance(node, ast.FunctionDef) and node.name == 'child_case')
        guards = [node.test for node in ast.walk(child) if isinstance(node, ast.Assert)
                  and any(isinstance(name, ast.Name) and name.id == 'manifest'
                          for name in ast.walk(node.test))]
        self.assertEqual(len(guards), 1)
        guard = compile(ast.Expression(guards[0]), str(path), 'eval')
        manifest = [path.name for path in sorted((root / 'db/migrations').glob('*.sql'))]
        def accepts(candidate):
            return eval(guard, {'__builtins__': {}, 'len': len}, {'manifest': candidate})
        self.assertTrue(accepts(manifest))
        for candidate in (manifest[:40], manifest + ['043_unreviewed.sql'],
                          manifest[:-1] + ['042_wrong.sql']):
            with self.subTest(manifest=candidate):
                self.assertFalse(accepts(candidate))
