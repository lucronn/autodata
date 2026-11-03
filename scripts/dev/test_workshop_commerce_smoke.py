import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/dev'))
from workshop_commerce_smoke import CASE_NAMES,ASSERTION_KEYS,junit_results,success,GO_ROOT,go_results


class CommerceCollectorTests(unittest.TestCase):
    def test_go_stream_requires_exact_real_root_without_skips_or_failures(self):
        events=[{'Action':'run','Test':GO_ROOT},{'Action':'pass','Test':GO_ROOT},{'Action':'pass'}]
        self.assertTrue(go_results(events))
        for extra in ({'Action':'skip','Test':'Other'},{'Action':'fail'}, {'Action':'pass','Test':'Other'}, {'Action':'skip','Test':GO_ROOT}):
            self.assertFalse(go_results(events+[extra]))
        self.assertFalse(go_results(events[1:]))

    def test_nonzero_timeout_or_missing_observation_cannot_pass(self):
        flags={key:True for key in ASSERTION_KEYS}
        self.assertTrue(success(0,False,flags))
        self.assertFalse(success(1,False,flags));self.assertFalse(success(0,True,flags))
        del flags[CASE_NAMES[0]];self.assertFalse(success(0,False,flags))

    def test_complete_junit_inventory_rejects_skips_failures_and_duplicates(self):
        def xml(extra='',change=''):
            cases=''.join(f'<testcase classname="tests.test_commerce_postgres" name="{name}">{change if i==0 else ""}</testcase>' for i,name in enumerate(CASE_NAMES))
            return '<testsuite>'+cases+extra+'</testsuite>'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.xml'
            path.write_text(xml());self.assertTrue(all(junit_results(path)[2].values()))
            for value in (xml(change='<skipped/>'),xml(change='<failure/>'),xml(change='<error/>'),
                xml(extra=f'<testcase classname="tests.test_commerce_postgres" name="{CASE_NAMES[0]}"/>'),'<testsuite/>'):
                path.write_text(value);self.assertFalse(all(junit_results(path)[2].values()))
            path.unlink();self.assertEqual(junit_results(path)[0],0)
