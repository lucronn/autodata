"""Offline evidence integrity and positional coverage, never display permission."""

from datetime import datetime, timezone
from hashlib import sha256
import base64
import json
import socket
import subprocess

import pytest

from autodata_ingestion.capture_audit import AuditError, audit, main


NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
SECRET = "PRIVATE-CONTENT-AND-CREDENTIAL-SENTINEL"
REF = "/opaque-asset?private=" + SECRET
URL = "/figure?private=" + SECRET


def digest(raw):
    return sha256(raw).hexdigest()


def write(root, path, value):
    path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    return digest(raw)


def envelope(content, **extra):
    return {"request_id": "00000000-0000-4000-8000-000000000001", "provider": "bankone",
        "source_revision": "private-revision", "fetched_at": "2026-11-05T12:00:00Z",
        "source_locator": "https://bankone.cars.tk/private-source", "kind": "article",
        "media_type": "text/html", "content": content, "sha256": digest(content.encode()), **extra}


def corpus(root, *, bound=True, binary=True):
    raw = f'<p>{SECRET}</p><img src="{URL}"><table><tr><td><img src="{URL}"></td></tr></table>'
    identity = digest(b"article-identity")
    env = envelope(raw, asset_resource_refs=[REF], **({"asset_bindings": [{"source_url": URL, "resource_ref": REF}]} if bound else {}))
    hashes = {"article/source-resource.bin": write(root, "article/source-resource.bin", raw.encode()),
              "article/source-envelope.json": write(root, "article/source-envelope.json", env)}
    meta = {"bank": "bankone", "identity_sha256": identity,
            "resource_sha256": hashes["article/source-resource.bin"], "envelope_sha256": hashes["article/source-envelope.json"]}
    hashes["article/metadata.json"] = write(root, "article/metadata.json", meta)
    selection = {"bank": "bankone", "identity_sha256": identity, "folder": "article",
        "descriptor": {"opaque_ref": "private-article", "title": SECRET, "resource_ref": "private-body"},
        "candidate": {"opaque_ref": "private-vehicle"}, "selector": {"year": 2024},
        "descriptor_envelope_sha256": "a" * 64, "resolution_envelope_sha256": "b" * 64}
    hashes["selection-manifest.json"] = write(root, "selection-manifest.json", {"selections": [selection]})
    write(root, "file-hashes.json", hashes)
    if binary:
        payload = b"\x89PNG\r\n\x1a\n" + SECRET.encode()
        asset = envelope("")
        asset.pop("content")
        asset.update(kind="asset", media_type="image/png", content_base64=base64.b64encode(payload).decode(), sha256=digest(payload))
        entry = {"provider": "bankone", "resource_ref": REF, "envelope_path": "assets/envelope.json",
            "payload_path": "assets/image.bin", "envelope_sha256": write(root, "assets/envelope.json", asset),
            "payload_sha256": write(root, "assets/image.bin", payload)}
        write(root, "audit-assets.json", {"resources": [entry]})
    return hashes


def add_rights(root, *, binary=True):
    covered = [digest((root / "article/source-resource.bin").read_bytes())]
    if binary:
        covered.append(digest((root / "assets/image.bin").read_bytes()))
    row = {"provider": "bankone", "resource_sha256": covered, "audience": "restricted_external_testers",
        "permitted_use": "display", "reviewer": SECRET, "valid_until": "2027-01-01T00:00:00Z",
        "evidence": {"path": "rights/private-record.txt", "sha256": write(root, "rights/private-record.txt", SECRET.encode())}}
    write(root, "audit-rights.json", {"records": [row]})
    return row


def replace_envelope(root, hashes, mutate):
    env = json.loads((root / "article/source-envelope.json").read_bytes())
    mutate(env)
    hashes["article/source-envelope.json"] = write(root, "article/source-envelope.json", env)
    meta = json.loads((root / "article/metadata.json").read_bytes())
    meta["envelope_sha256"] = hashes["article/source-envelope.json"]
    hashes["article/metadata.json"] = write(root, "article/metadata.json", meta)
    write(root, "file-hashes.json", hashes)


def test_repeated_nested_positions_share_one_retained_asset_and_stay_private(tmp_path, monkeypatch):
    corpus(tmp_path)
    def forbidden(*a, **k):
        raise AssertionError("No socket or subprocess may be constructed")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = audit(tmp_path, as_of=NOW)
    item = result["articles"][0]
    assert item["integrity"] and item["adapted"] and item["local_capture_complete"]
    assert item["declared_assets"] == 1
    assert result["summary"]["image_positions"] == result["summary"]["positions_with_binary"] == 2
    assert item["positions"][0]["ref_sha256"] == item["positions"][1]["ref_sha256"]
    assert item["rights"]["status"] == "UNKNOWN"
    assert not result["external_display_allowed"] and not item["external_display_allowed"]
    assert SECRET not in json.dumps(result) and URL not in json.dumps(result)


def test_missing_binding_never_infers_position_from_declared_asset_order(tmp_path):
    corpus(tmp_path, bound=False)
    item = audit(tmp_path, as_of=NOW)["articles"][0]
    assert len(item["positions"]) == 2
    assert all(p["reason"] == "UNBOUND_POSITION" and not p["binary_present"] for p in item["positions"])
    assert not item["local_capture_complete"] and item["missing_binaries"] == 0


def test_missing_binary_preserves_position_and_distinct_asset_counts(tmp_path):
    corpus(tmp_path, binary=False)
    result = audit(tmp_path, as_of=NOW)
    assert result["summary"]["bound_positions"] == 2
    assert result["summary"]["positions_with_binary"] == 0
    assert result["summary"]["missing_binaries"] == 1
    assert all(p["reason"] == "LOCAL_BINARY_MISSING" for p in result["articles"][0]["positions"])


def test_cli_truthfully_reports_incomplete_capture_without_error_exit(tmp_path, capsys):
    corpus(tmp_path, binary=False)
    assert main([str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["summary"]["missing_binaries"] == 1
    assert result["summary"]["local_capture_complete"] == 0
    assert not result["external_display_allowed"]


def test_forged_sidecar_cannot_bind_undeclared_ref(tmp_path):
    hashes = corpus(tmp_path)
    replace_envelope(tmp_path, hashes, lambda e: e["asset_bindings"][0].update(resource_ref="forged-" + SECRET))
    item = audit(tmp_path, as_of=NOW)["articles"][0]
    assert item["errors"] == ["ENVELOPE_INVALID"] and not item["integrity"]
    assert not item["local_capture_complete"] and SECRET not in json.dumps(item)


@pytest.mark.parametrize("path", ["article/source-resource.bin", "article/source-envelope.json", "article/metadata.json", "selection-manifest.json"])
def test_hash_mismatch_fails_closed_without_printing_bytes(tmp_path, path, capsys):
    corpus(tmp_path)
    (tmp_path / path).write_text(SECRET)
    assert main([str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert SECRET not in out and "HASH_MISMATCH" in out
    assert json.loads(out)["external_display_allowed"] is False


def test_declared_envelope_bytes_must_equal_separately_retained_body(tmp_path):
    hashes = corpus(tmp_path)
    replace_envelope(tmp_path, hashes, lambda e: e.update(content="forged content", sha256=digest(b"forged content")))
    assert audit(tmp_path, as_of=NOW)["articles"][0]["errors"] == ["ENVELOPE_BODY_MISMATCH"]


def test_foreign_provider_asset_envelope_rejected(tmp_path):
    corpus(tmp_path)
    path = tmp_path / "assets/envelope.json"
    env = json.loads(path.read_bytes())
    env["provider"] = "banktwo"
    rows = json.loads((tmp_path / "audit-assets.json").read_bytes())
    rows["resources"][0]["envelope_sha256"] = write(tmp_path, "assets/envelope.json", env)
    write(tmp_path, "audit-assets.json", rows)
    item = audit(tmp_path, as_of=NOW)["articles"][0]
    assert item["errors"] == ["ENVELOPE_INVALID"] and not item["local_capture_complete"]


def test_rights_hash_references_are_reported_without_granting_permission(tmp_path):
    corpus(tmp_path)
    row = add_rights(tmp_path)
    result = audit(tmp_path, as_of=NOW)
    rights = result["articles"][0]["rights"]
    assert rights["status"] == "EVIDENCE_REFERENCED"
    assert rights["evidence_sha256"] == [row["evidence"]["sha256"]]
    assert not rights["permission_verified"] and not result["external_display_allowed"]
    assert SECRET not in json.dumps(result) and "private-record" not in json.dumps(result)


@pytest.mark.parametrize("change,status", [
    ({"provider": "banktwo"}, "UNKNOWN"),
    ({"resource_sha256": ["f" * 64]}, "UNKNOWN"),
    ({"valid_until": "2020-01-01T00:00:00Z"}, "INVALID_EVIDENCE"),
    ({"audience": "public"}, "INVALID_EVIDENCE"),
    ({"reviewer": ""}, "INVALID_EVIDENCE"),
])
def test_wrong_scope_or_invalid_rights_never_become_display_permission(tmp_path, change, status):
    corpus(tmp_path)
    row = add_rights(tmp_path)
    row.update(change)
    write(tmp_path, "audit-rights.json", {"records": [row]})
    result = audit(tmp_path, as_of=NOW)
    assert result["articles"][0]["rights"]["status"] == status
    assert result["external_display_allowed"] is False


def test_rights_must_cover_asset_hashes_and_evidence_bytes(tmp_path):
    corpus(tmp_path)
    add_rights(tmp_path, binary=False)
    assert audit(tmp_path, as_of=NOW)["articles"][0]["rights"]["status"] == "UNKNOWN"
    add_rights(tmp_path)
    (tmp_path / "rights/private-record.txt").write_text("changed evidence")
    assert audit(tmp_path, as_of=NOW)["articles"][0]["rights"]["status"] == "INVALID_EVIDENCE"


@pytest.mark.parametrize("target", ["assets/image.bin", "rights/private-record.txt"])
def test_symlink_files_are_not_followed(tmp_path, target):
    corpus(tmp_path)
    add_rights(tmp_path)
    path = tmp_path / target
    external = tmp_path.parent / (tmp_path.name + "-external")
    external.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(external)
    item = audit(tmp_path, as_of=NOW)["articles"][0]
    if target.startswith("assets"):
        assert not item["local_capture_complete"]
    else:
        assert item["rights"]["status"] == "INVALID_EVIDENCE"
    assert item["external_display_allowed"] is False


def test_asset_tamper_and_duplicate_manifest_rejected(tmp_path):
    corpus(tmp_path)
    (tmp_path / "assets/image.bin").write_bytes(b"tampered")
    assert audit(tmp_path, as_of=NOW)["articles"][0]["errors"] == ["HASH_MISMATCH"]
    rows = json.loads((tmp_path / "audit-assets.json").read_bytes())["resources"]
    write(tmp_path, "audit-assets.json", {"resources": rows * 2})
    with pytest.raises(AuditError, match="ASSET_MANIFEST_INVALID"):
        audit(tmp_path, as_of=NOW)


def test_parent_traversal_and_malformed_json_never_leak_input(tmp_path, capsys):
    corpus(tmp_path)
    assets = json.loads((tmp_path / "audit-assets.json").read_bytes())
    assets["resources"][0]["payload_path"] = "../" + SECRET
    write(tmp_path, "audit-assets.json", assets)
    assert audit(tmp_path, as_of=NOW)["articles"][0]["errors"] == ["LOCAL_PATH_INVALID"]
    (tmp_path / "file-hashes.json").write_text('{"private": "' + SECRET + '"')
    assert main([str(tmp_path)]) == 2
    assert SECRET not in capsys.readouterr().out
