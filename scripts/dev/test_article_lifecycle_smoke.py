import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

spec=importlib.util.spec_from_file_location("lifecycle_smoke",Path(__file__).with_name("article_lifecycle_smoke.py"))
smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)


def test_junit_does_not_treat_skips_as_acceptance(tmp_path):
    path=tmp_path/"fixture.xml"
    path.write_text('<testsuites><testsuite><testcase classname="fixture" name="available"/><testcase classname="fixture" name="missing"><skipped/></testcase><testcase name="failed"><failure/></testcase><testcase name="outage"><error/></testcase></testsuite></testsuites>')
    measured=smoke.junit_measurements(path)
    assert {key:measured[key] for key in ("tests","failures","errors","skipped")}=={"tests":4,"failures":1,"errors":1,"skipped":1}
    assert measured["test_ids"][0]=="fixture.available"


def test_candidate_provenance_is_explicit_when_container_has_no_git():
    with patch.object(smoke.subprocess,"run",side_effect=FileNotFoundError):
        with pytest.raises(ValueError):smoke.candidate_identity(None)
        result=smoke.candidate_identity("a"*40)
        assert result["sha"]=="a"*40
        assert "host-supplied" in result["source"]


def test_smoke_rejects_non_fixture_execution(monkeypatch,tmp_path):
    monkeypatch.delenv("AUTODATA_LIFECYCLE_TEST",raising=False)
    with pytest.raises(SystemExit):smoke.main(["--mode","fixture","--output",str(tmp_path/"evidence.json")])
