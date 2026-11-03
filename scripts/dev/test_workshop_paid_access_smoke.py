from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from workshop_paid_access_smoke import GO_NAMES, CASE_IDS, CASE_ASSERTIONS, junit_valid, go_valid, success

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
