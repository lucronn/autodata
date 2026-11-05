"""Command boundary tests; never connect to a real database."""
import importlib.util
import json
from pathlib import Path
import pytest

PATH=Path(__file__).with_name('article_content_review.py')


def load():
    spec=importlib.util.spec_from_file_location('review_cli',PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_cli_requires_all_expected_bindings_before_opening_database():
    module=load()
    with pytest.raises(SystemExit) as error:module.main(['approve'])
    assert error.value.code==2


def test_cli_export_prints_only_hash_manifest(monkeypatch,capsys,tmp_path):
    module=load()
    expected=dict(job_id='00000000-0000-0000-0000-000000000001',article_id='00000000-0000-0000-0000-000000000002',
        source_revision_id='00000000-0000-0000-0000-000000000003',candidate_revision_id='00000000-0000-0000-0000-000000000004',
        request_generation=3,profile_version='full-prose-review-v1',normalization_version='ordered-article-v1',
        identity_key='bankone:synthetic',source_fingerprint='a'*64,source_hash='b'*64,candidate_hash='c'*64)
    manifest=tmp_path/'binding.json';manifest.write_text(json.dumps(expected));manifest.chmod(0o600)
    calls=[]
    def export(repo,**kwargs):
        calls.append(kwargs);return {'status':'exported','bindings':kwargs['expected']}
    monkeypatch.setattr(module,'export_review',export)
    assert module.main(['export','--expected',str(manifest),'--output',str(tmp_path/'private')],repo=object())==0
    assert calls==[dict(expected=expected,destination=tmp_path/'private')]
    assert json.loads(capsys.readouterr().out)['status']=='exported'


def test_approve_requires_explicit_complete_content_attestation(tmp_path):
    module=load()
    with pytest.raises(SystemExit):module.main(['approve','--expected','missing','--reviewer','human','--allowlist','missing','--rationale','Reviewed all complete source instructions carefully.'],repo=object())


def test_cli_never_echoes_exception_body(capsys):
    module=load()
    def failure():raise RuntimeError('PRIVATE source body')
    assert module.run_safely(failure)==1
    output=capsys.readouterr()
    assert 'PRIVATE' not in output.err
    assert json.loads(output.err)=={'status':'error','code':'CONTENT_REVIEW_FAILED'}
