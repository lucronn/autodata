from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from consumer_agent import ChatHTTPClient, ConsumerHTTPError, aggregate_decision, create_or_reuse_issue, consumer_projection, run_case, run_cases, score_response


ROOT = Path(__file__).parents[2]


def test_consumer_agent_is_registered_with_report_only_capability():
    registry = json.loads((ROOT / ".autodata-agent-registry.json").read_text())
    matches = [agent for agent in registry["agents"] if agent["name"] == "autodata-consumer-agent"]

    assert len(matches) == 1
    agent = matches[0]
    assert (ROOT / agent["prompt"]).is_file()
    assert agent["can_merge"] is False
    assert agent["can_deploy"] == []
    assert "reports" in " ".join(agent["can_write"])


def _complete_response():
    return {
        "query_id": "query-12345678",
        "status": "available",
        "answer": {
            "vehicle": {"vehicle_id": "vehicle-1", "make": "Toyota", "model": "Camry", "year": 2005},
            "procedure": {
                "title": "Starter Replacement Guide",
                "applicability": "2005 Toyota Camry",
                "content_status": "complete",
                "pdf_ready": True,
                "review_state": "UNREVIEWED",
                "review_label": "UNREVIEWED — human review pending",
                "revision_id": "guide:revision-1",
                "steps": [
                    {"phase": "removal", "components": ["starter"], "action": "Remove the starter.", "instructions": ["Disconnect the battery first."], "images": [{"url": "https://example.test/figure.png"}]},
                    {"phase": "installation", "components": ["starter"], "action": "Install the starter.", "instructions": ["Tighten the mounting bolts."], "images": [{"url": "https://example.test/figure-2.png"}]},
                ],
                "warnings": [],
            },
            "pdf": {"ready": True, "revision_id": "guide:revision-1"},
        },
    }


def test_consumer_projection_omits_internal_source_material():
    response = {**_complete_response(), "answer": {**_complete_response()["answer"], "source_unnormalized": {"raw_html": "secret"}, "worker_stream": [{"token": "secret"}]}}
    projection = consumer_projection(response)
    encoded = json.dumps(projection)
    assert "raw_html" not in encoded
    assert "worker_stream" not in encoded
    assert "secret" not in encoded
    assert "source_" not in encoded
    assert "evidence" not in encoded
    assert "worker_stream" not in encoded
    assert projection["answer"]["procedure"]["title"] == "Starter Replacement Guide"


def test_score_response_passes_complete_illustrated_answer():
    result = score_response(
        {"name": "camry-starter", "message": "replace starter", "expected_vehicle": {"vehicle_id": "vehicle-1"}, "expected_components": ["starter"], "min_steps": 2, "min_figures": 2},
        _complete_response(),
        pdf_response=b"%PDF-1.7 test",
    )
    assert result["decision"] == "pass"
    assert result["score"] == 100
    assert result["findings"] == []


def test_score_response_marks_partial_answer_for_review():
    response = _complete_response()
    response["answer"]["procedure"]["content_status"] = "partial"
    response["answer"]["procedure"]["pdf_ready"] = False
    response["answer"]["pdf"] = {"ready": False}
    result = score_response(
        {"name": "partial", "message": "replace starter", "expected_vehicle": {"vehicle_id": "vehicle-1"}, "expected_components": ["starter"], "min_steps": 2, "min_figures": 2},
        response,
    )
    assert result["decision"] == "needs_review"
    assert any(finding["finding_id"] == "partial:procedure:coverage" for finding in result["findings"])


def test_score_response_requires_case_declared_procedure_depth_terms():
    result = score_response(
        {
            "name": "depth-check",
            "message": "replace starter",
            "expected_vehicle": {"vehicle_id": "vehicle-1"},
            "expected_components": ["starter"],
            "min_steps": 2,
            "min_figures": 2,
            "required_terms": ["torque", "check"],
        },
        _complete_response(),
        pdf_response=b"%PDF-1.7 test",
    )
    assert result["decision"] == "needs_review"
    assert result["dimensions"]["procedure_coverage"]["passed"] is False
    assert any(finding["finding_id"] == "depth-check:procedure:required-terms" for finding in result["findings"])


class FakeChatClient:
    def __init__(self):
        self.polls = 0
        self.selected = []

    def create(self, _message, _idempotency_key):
        return {"query_id": "query-12345678", "status": "awaiting_vehicle", "vehicle_options": [{"option_number": 1, "vehicle_id": "vehicle-1"}]}

    def select(self, query_id, option_number, _idempotency_key):
        self.selected.append((query_id, option_number))
        return {"query_id": query_id, "status": "processing"}

    def get(self, _query_id):
        self.polls += 1
        return _complete_response() if self.polls > 1 else {"query_id": "query-12345678", "status": "processing"}

    def pdf(self, _query_id):
        return b"%PDF-1.7 test"


class TransientPollingClient(FakeChatClient):
    def get(self, query_id):
        self.polls += 1
        if self.polls == 1:
            raise ConsumerHTTPError("chat API returned HTTP 502", 502)
        return _complete_response()


def test_run_case_retries_transient_poll_error_until_answer_is_available():
    result = run_case(
        TransientPollingClient(),
        {"name": "camry-starter", "message": "replace starter", "expected_vehicle": {"vehicle_id": "vehicle-1"}, "expected_components": ["starter"], "min_steps": 2, "min_figures": 2},
        poll_interval=0.01,
        timeout=1,
    )
    assert result["review"]["decision"] == "pass"


def test_run_case_selects_vehicle_and_records_revision_hash():
    client = FakeChatClient()
    result = run_case(client, {"name": "camry-starter", "message": "replace starter", "expected_vehicle": {"vehicle_id": "vehicle-1"}, "expected_components": ["starter"], "min_steps": 2, "min_figures": 2, "expected_decision": "pass"}, poll_interval=0.01, timeout=1)
    assert result["review"]["decision"] == "pass"
    assert result["selected_vehicle"] is True
    assert client.selected == [("query-12345678", 1)]
    assert result["response_sha256"]
    assert result["pdf_sha256"]
    assert result["expected_decision"] == "pass"
    assert result["expectation_met"] is True


def test_http_client_bounds_and_parses_json_without_logging_auth_material():
    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b'{"query_id":"query-12345678","status":"processing"}'

    def opener(request, timeout):
        seen.append((request.get_method(), request.full_url, dict(request.headers), timeout))
        return Response()

    client = ChatHTTPClient("http://127.0.0.1:8080", opener=opener, auth_token="must-not-appear")
    result = client.create("replace starter", "review-key")

    assert result["status"] == "processing"
    assert seen[0][0:2] == ("POST", "http://127.0.0.1:8080/chat/queries")
    assert seen[0][2]["Idempotency-key"] == "review-key"
    assert seen[0][2]["Authorization"] == "Bearer must-not-appear"
    assert seen[0][3] == 20


def test_run_cases_records_aggregate_decision_and_does_not_call_github_for_pass():
    with TemporaryDirectory() as directory:
        report = run_cases(
            [{"name": "camry-starter", "message": "replace starter", "expected_vehicle": {"vehicle_id": "vehicle-1"}, "expected_components": ["starter"], "min_steps": 2, "min_figures": 2}],
            client=FakeChatClient(),
            implementation_sha="a" * 40,
            report_dir=Path(directory),
            repository="lucronn/autodata",
            create_issues=False,
        )

        assert report["decision"] == "pass"
        assert report["summary"]["pass"] == 1
        assert report["issue_actions"] == []
        assert Path(report["report_path"]).is_file()
        persisted = json.loads(Path(report["report_path"]).read_text())
        assert persisted["decision"] == "pass"


def test_run_cases_passes_timeout_to_each_case_poll(monkeypatch):
    observed = []

    def fake_run_case(_client, case, *, idempotency_prefix, timeout):
        observed.append((case["name"], idempotency_prefix, timeout))
        return {"review": {"decision": "pass"}}

    monkeypatch.setattr("consumer_agent.run_case", fake_run_case)
    with TemporaryDirectory() as directory:
        run_cases(
            [{"name": "forester", "message": "replace pump"}],
            client=FakeChatClient(),
            implementation_sha="a" * 40,
            report_dir=Path(directory),
            timeout=300,
        )

    assert observed[0][0] == "forester"
    assert observed[0][2] == 300


def test_issue_creation_reuses_stable_finding_marker():
    finding = {"finding_id": "camry-starter:procedure:coverage", "severity": "high", "category": "quality", "message": "missing installation", "reproduction": "replace starter"}
    with TemporaryDirectory() as directory:
        report = {"case": "camry-starter", "implementation_sha": "a" * 40, "report_path": str(Path(directory) / "report.json"), "response_sha256": "b" * 64}
        calls = []

        def first_gh(args):
            calls.append(args)
            if args[1] == "list":
                return "[]"
            return "https://github.com/lucronn/autodata/issues/123"

        created = create_or_reuse_issue(finding, report, repository="lucronn/autodata", gh_runner=first_gh)
        assert created["action"] == "created"
        marker = created["marker"]

        def second_gh(args):
            calls.append(args)
            return json.dumps([{"number": 123, "body": marker}])

        reused = create_or_reuse_issue(finding, report, repository="lucronn/autodata", gh_runner=second_gh)
        assert reused["action"] == "reused"
        assert reused["issue_number"] == 123
        assert any(args[1] == "create" for args in calls)


def test_cli_decision_mapping_preserves_blocked_aggregate_state():
    assert aggregate_decision({"pass": 2, "fail": 0, "needs_review": 0, "blocked": 2}) == "blocked"
    assert aggregate_decision({"pass": 2, "fail": 1, "needs_review": 0, "blocked": 0}) == "fail"
    assert aggregate_decision({"pass": 2, "fail": 0, "needs_review": 1, "blocked": 0}) == "needs_review"
    assert aggregate_decision({"pass": 2, "fail": 0, "needs_review": 0, "blocked": 0}) == "pass"
