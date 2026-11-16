"""Offline capture inventory. Local evidence never authorizes external display.

Run with ``python -m autodata_ingestion.capture_audit CAPTURE_ROOT``. The root
uses the retained selection-manifest.json/file-hashes.json capture layout.
Optional audit-assets.json and audit-rights.json are described in the canonical
audit document. No connector client, object store, subprocess or network is used.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import PurePosixPath
import re
import stat
from uuid import NAMESPACE_URL, UUID, uuid5

from .article_lifecycle_types import ArticleKey, SourceArticleContext
from .source_adapters import adapt_bound_article
from .source_article_capture import _image_nodes
from .source_connector_client import SourceConnectorError, _validated_envelope, _valid_ref_list


HASH = re.compile(r"[a-f0-9]{64}\Z")
LIMIT = 20_000_000


class AuditError(ValueError):
    """Only fixed, content-free codes may reach the command's output."""


def require(condition, code):
    if not condition:
        raise AuditError(code)


def read_local(root, relative):
    """Open regular bounded files beneath root, refusing symlink traversal."""
    require(isinstance(relative, str) and bool(relative), "LOCAL_PATH_INVALID")
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and ".." not in parts.parts and bool(parts.parts), "LOCAL_PATH_INVALID")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(parts.parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(parts.parts) - 1:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= LIMIT, "LOCAL_FILE_INVALID")
        chunks, size = [], 0
        while size <= LIMIT:
            chunk = os.read(fd, min(65536, LIMIT + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        require(size <= LIMIT, "LOCAL_FILE_INVALID")
        return b"".join(chunks)
    finally:
        os.close(fd)


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "DUPLICATE_JSON_KEY")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


def checked(root, path, expected):
    require(isinstance(expected, str) and HASH.fullmatch(expected), "EXPECTED_HASH_INVALID")
    raw = read_local(root, path)
    require(sha256(raw).hexdigest() == expected, "HASH_MISMATCH")
    return raw


def resource(root, envelope_path, payload_path, envelope_hash, payload_hash, provider):
    raw = checked(root, envelope_path, envelope_hash)
    payload = checked(root, payload_path, payload_hash)
    # This is the same pure validator used after an authenticated connector read.
    # It validates the embedded bytes as well as the declared hash and sidecar.
    env = _validated_envelope(decode(raw), "resource", provider, None, "offline:retained-resource")
    require(env.raw_resource == payload, "ENVELOPE_BODY_MISMATCH")
    return env


def optional(root, name, default):
    try:
        return decode(read_local(root, name))
    except FileNotFoundError:
        return default


def rights_evidence(root, records, provider, content_hashes, as_of):
    matches, invalid = [], False
    for row in records:
        if not isinstance(row, dict) or row.get("provider") != provider:
            continue
        try:
            require(set(row) == {"provider", "resource_sha256", "audience", "permitted_use", "reviewer", "valid_until", "evidence"}, "RIGHTS_EVIDENCE_INVALID")
            covered = row["resource_sha256"]
            require(isinstance(covered, list) and 0 < len(covered) <= 1000 and all(isinstance(x, str) and HASH.fullmatch(x) for x in covered), "RIGHTS_EVIDENCE_INVALID")
            if not content_hashes <= set(covered):
                continue
            require(row["audience"] == "restricted_external_testers" and row["permitted_use"] == "display", "RIGHTS_EVIDENCE_INVALID")
            require(isinstance(row["reviewer"], str) and 0 < len(row["reviewer"].strip()) <= 256, "RIGHTS_EVIDENCE_INVALID")
            until = datetime.fromisoformat(row["valid_until"].replace("Z", "+00:00"))
            require(until.tzinfo is not None and until >= as_of, "RIGHTS_EVIDENCE_INVALID")
            evidence = row["evidence"]
            require(isinstance(evidence, dict) and set(evidence) == {"path", "sha256"}, "RIGHTS_EVIDENCE_INVALID")
            require(bool(checked(root, evidence["path"], evidence["sha256"])), "RIGHTS_EVIDENCE_INVALID")
            matches.append(evidence["sha256"])
        except (AuditError, OSError, ValueError, TypeError, AttributeError):
            invalid = True
    # Even complete references are assertions for review, not legal approval.
    return {"status": "EVIDENCE_REFERENCED" if matches else "INVALID_EVIDENCE" if invalid else "UNKNOWN",
            "evidence_sha256": sorted(set(matches)), "permission_verified": False}


def audit_article(root, selection, hashes, assets, rights, as_of):
    provider = selection.get("bank")
    identity = selection.get("identity_sha256")
    require(provider in {"bankone", "banktwo"} and isinstance(identity, str) and HASH.fullmatch(identity), "SELECTION_INVALID")
    result = {"provider": provider, "identity_sha256": identity, "integrity": False,
              "adapted": False, "positions": [], "declared_assets": 0,
              "missing_binaries": 0, "local_capture_complete": False,
              "rights": {"status": "UNKNOWN", "evidence_sha256": [], "permission_verified": False},
              "external_display_allowed": False, "errors": []}
    try:
        folder = selection["folder"]
        require(isinstance(folder, str), "SELECTION_INVALID")
        meta_path, env_path, body_path = (folder + "/" + name for name in ("metadata.json", "source-envelope.json", "source-resource.bin"))
        meta = decode(checked(root, meta_path, hashes.get(meta_path)))
        require(meta["bank"] == provider and meta["identity_sha256"] == identity, "SELECTION_INVALID")
        env = resource(root, env_path, body_path, hashes.get(env_path), hashes.get(body_path), provider)
        require(meta["envelope_sha256"] == hashes[env_path] and meta["resource_sha256"] == hashes[body_path], "HASH_MISMATCH")
        result.update(integrity=True, resource_sha256=hashes[body_path], envelope_sha256=hashes[env_path])
        descriptor = selection["descriptor"]
        key = ArticleKey(provider, uuid5(NAMESPACE_URL, "private-acceptance:" + provider + ":" + selection["candidate"]["opaque_ref"]),
                         None, selection["candidate"]["opaque_ref"], descriptor["opaque_ref"])
        context = SourceArticleContext(key, selection["selector"], descriptor,
            UUID(selection["descriptor_envelope_sha256"][:32]), UUID(selection["resolution_envelope_sha256"][:32]), (hashes[body_path],))
        adapted = adapt_bound_article(env.to_source_resource(), context)
        result["adapted"] = True
        declared = []
        for refs in (descriptor.get("asset_resource_refs", []), env.body.get("asset_resource_refs", []), adapted.get("asset_resource_refs", [])):
            require(_valid_ref_list(refs, 128), "DECLARED_REFS_INVALID")
            declared.extend(refs)
        declared = set(declared)
        result["declared_assets"] = len(declared)
        available, asset_hashes = {}, set()
        for ref in sorted(declared):
            entry = assets.get((provider, ref))
            if entry is None:
                available[ref] = False
                continue
            asset = resource(root, entry["envelope_path"], entry["payload_path"], entry["envelope_sha256"], entry["payload_sha256"], provider)
            require(asset.body["kind"] in {"asset", "binary"} and asset.body["media_type"].startswith("image/"), "ASSET_TYPE_INVALID")
            available[ref] = True
            asset_hashes.add(entry["payload_sha256"])
        result["missing_binaries"] = sum(not present for present in available.values())
        for index, node in enumerate(_image_nodes(adapted["blocks"]), 1):
            ref = node.get("asset_resource_ref")
            if not ref and node.get("url") in declared:
                ref = node["url"]
            bound = isinstance(ref, str) and ref in declared
            reason = "UNDECLARED_REF" if ref and not bound else "UNBOUND_POSITION" if not bound else "LOCAL_BINARY_MISSING" if not available[ref] else None
            result["positions"].append({"position": index, "bound": bound,
                "ref_sha256": sha256(ref.encode()).hexdigest() if isinstance(ref, str) else None,
                "binary_present": bound and available[ref], "reason": reason})
        result["rights"] = rights_evidence(root, rights, provider, {hashes[body_path]} | asset_hashes, as_of)
        result["local_capture_complete"] = all(p["bound"] and p["binary_present"] for p in result["positions"]) and result["missing_binaries"] == 0
    except AuditError as error:
        result["errors"].append(str(error))
    except SourceConnectorError:
        result["errors"].append("ENVELOPE_INVALID")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        result["errors"].append("CAPTURE_INVALID")
    return result


def audit(root, *, as_of=None):
    as_of = as_of or datetime.now(timezone.utc)
    require(as_of.tzinfo is not None, "AS_OF_INVALID")
    hashes_raw = read_local(root, "file-hashes.json")
    hashes = decode(hashes_raw)
    require(isinstance(hashes, dict), "HASH_MANIFEST_INVALID")
    raw = checked(root, "selection-manifest.json", hashes.get("selection-manifest.json"))
    selections = decode(raw)["selections"]
    require(isinstance(selections, list) and 0 < len(selections) <= 1000, "SELECTION_INVALID")
    asset_rows = optional(root, "audit-assets.json", {"resources": []})
    rights_rows = optional(root, "audit-rights.json", {"records": []})
    require(isinstance(asset_rows, dict) and set(asset_rows) == {"resources"} and isinstance(asset_rows["resources"], list) and len(asset_rows["resources"]) <= 10000, "ASSET_MANIFEST_INVALID")
    require(isinstance(rights_rows, dict) and set(rights_rows) == {"records"} and isinstance(rights_rows["records"], list) and len(rights_rows["records"]) <= 1000, "RIGHTS_MANIFEST_INVALID")
    assets = {}
    for row in asset_rows["resources"]:
        require(isinstance(row, dict) and set(row) == {"provider", "resource_ref", "envelope_path", "payload_path", "envelope_sha256", "payload_sha256"}, "ASSET_MANIFEST_INVALID")
        require(row["provider"] in {"bankone", "banktwo"} and _valid_ref_list([row["resource_ref"]], 1), "ASSET_MANIFEST_INVALID")
        key = row["provider"], row["resource_ref"]
        require(key not in assets, "ASSET_MANIFEST_INVALID")
        assets[key] = row
    articles, seen = [], set()
    for selection in selections:
        require(isinstance(selection, dict), "SELECTION_INVALID")
        identity = selection.get("identity_sha256")
        require(isinstance(identity, str) and identity not in seen, "SELECTION_INVALID")
        seen.add(identity)
        articles.append(audit_article(root, selection, hashes, assets, rights_rows["records"], as_of))
    counts = Counter()
    for item in articles:
        counts.update(articles=1, integrity_verified=int(item["integrity"]), adapted=int(item["adapted"]),
            image_positions=len(item["positions"]), bound_positions=sum(x["bound"] for x in item["positions"]),
            positions_with_binary=sum(x["binary_present"] for x in item["positions"]), missing_binaries=item["missing_binaries"],
            local_capture_complete=int(item["local_capture_complete"]), rights_evidence_referenced=int(item["rights"]["status"] == "EVIDENCE_REFERENCED"), errors=len(item["errors"]))
    return {"schema_version": 1, "as_of": as_of.isoformat(), "selection_manifest_sha256": sha256(raw).hexdigest(),
            "file_hash_manifest_sha256": sha256(hashes_raw).hexdigest(), "summary": dict(counts), "articles": articles,
            "external_display_allowed": False, "origin_authenticated": False,
            "limits": ["LOCAL_HASH_PINS_ARE_NOT_AUTHENTICATED_ORIGIN", "RIGHTS_REFERENCES_REQUIRE_INDEPENDENT_REVIEW", "NO_EXTERNAL_DISPLAY_ACCEPTANCE", "NO_LIVE_CATALOG_OR_PERSISTENCE_PROOF", "NO_IMAGE_DECODE_OR_RENDER_ACCEPTANCE"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root")
    args = parser.parse_args(argv)
    try:
        result = audit(args.capture_root)
        code = 2 if result["summary"]["errors"] else 0
    except AuditError as error:
        result, code = {"error": str(error), "external_display_allowed": False}, 2
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        result, code = {"error": "AUDIT_INPUT_INVALID", "external_display_allowed": False}, 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
