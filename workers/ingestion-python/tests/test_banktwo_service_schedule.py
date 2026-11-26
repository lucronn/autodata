import json
from dataclasses import replace

from autodata_ingestion.banktwo_service_schedule import banktwo_service_schedule
from autodata_ingestion.source_article_capture import capture_source_article
from test_source_article_capture import capture_fixture


def body(schedule, *, category="Service Intervals"):
    return json.dumps({"_embedded": {"ancestors": [
        {"type": "Component", "title": "Vehicle"},
        {"type": "Component", "title": "Maintenance"},
        {"type": "InformationType", "title": category},
        {"type": "InformationType", "title": schedule},
    ]}}).encode()


def test_reads_authored_schedule_from_maintenance_ancestors():
    assert banktwo_service_schedule(body("Normal Service")) == "Normal Service"
    assert banktwo_service_schedule(body("Severe Service")) == "Severe Service"


def test_does_not_infer_schedule_from_body_or_unrelated_context():
    assert banktwo_service_schedule(b'{"title":"Severe Service"}') is None
    assert banktwo_service_schedule(body("Normal Service", category="Service Procedures")) is None
    assert banktwo_service_schedule(body("Unknown Service")) is None
    assert banktwo_service_schedule(b'{"_embedded":{"ancestors":[{},{},null]}}') is None
    assert banktwo_service_schedule(b"<html>Severe Service</html>") is None


def test_retained_capture_carries_schedule_with_original_source(capture_fixture):
    envelope = json.loads(body("Severe Service"))
    envelope["_embedded"]["data"] = {"article": {"content": "<p>Follow the maintenance checklist.</p>"}}
    raw = json.dumps(envelope).encode()
    capture_fixture.body("banktwo", raw, "application/hal+json")
    context = capture_fixture.context("banktwo")
    context = replace(context, descriptor={**context.descriptor, "category": "Service Intervals"})
    result = capture_source_article(context, registry=capture_fixture.registry, object_store=capture_fixture.objects)
    assert result.service_schedule == "Severe Service"
    assert result.source_body == "Follow the maintenance checklist."
    assert "banktwo_service_schedule" not in result.resource_manifest[0]
