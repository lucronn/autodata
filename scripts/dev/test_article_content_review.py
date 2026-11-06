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


def test_failed_export_requires_explicit_attempt_bindings(monkeypatch,tmp_path,capsys):
    module = load()
    expected = {'profile_version':'full-prose-review-v1'}
    monkeypatch.setattr(module,'_expected',lambda path:expected)
    calls=[]
    def export(repo,**kwargs):
        calls.append(kwargs)
        return {'status':'exported'}
    monkeypatch.setattr(module,'export_failed_review',export,raising=False)
    attempt='00000000-0000-0000-0000-000000000005'
    assert module.main(['export-failed','--expected','private','--output',str(tmp_path/'private'),
        '--failed-attempt-id',attempt,'--failed-response-hash','a'*64],repo=object()) == 0
    assert calls[0]['failed_attempt_id'] == attempt
    assert calls[0]['failed_response_hash'] == 'a'*64
    assert json.loads(capsys.readouterr().out) == {'status':'exported'}


def test_correct_failed_appends_correction_without_approval_option(monkeypatch,tmp_path,capsys):
    module=load();calls=[]
    monkeypatch.setattr(module,'_expected',lambda path:{'candidate_hash':'b'*64})
    monkeypatch.setattr(module,'_read_private_json',lambda path:{'introduction':'A source-bound introduction.','replacements':[]})
    def correct(repo,**kwargs):
        calls.append(kwargs);return {'status':'rejected','review_id':'fixture'}
    monkeypatch.setattr(module,'record_failed_correction',correct)
    attempt='00000000-0000-0000-0000-000000000005'
    argv=['correct-failed','--expected','private','--failed-attempt-id',attempt,'--failed-response-hash','a'*64,
        '--reviewer','alice','--allowlist','private','--rationale','Compared the full original source carefully.','--corrections','private']
    assert module.main(argv,repo=object()) == 0
    assert calls[0]['failed_response_hash'] == 'a'*64
    assert 'decision' not in calls[0] and 'full_content_reviewed' not in calls[0]
    assert json.loads(capsys.readouterr().out)['status']=='rejected'
    with pytest.raises(SystemExit): module.main(argv+['--decision','APPROVED'],repo=object())


@pytest.mark.parametrize('command',['export-failed','correct-failed'])
def test_failed_commands_require_attempt_and_response_hash(command):
    module=load()
    with pytest.raises(SystemExit): module.main([command,'--expected','private'],repo=object())
