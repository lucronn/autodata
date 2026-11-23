"""Stage authenticated SVG responses for a single retained article repair."""

from base64 import b64encode
import json
import os
from pathlib import Path

from psycopg.rows import dict_row

from .article_content_review import _outside_git, _private_path, _read_private_json
from .source_connector_client import _validated_envelope
from .source_media_replay import _MAX_RESOURCES, _MAX_TOTAL_BYTES
from .source_table_replay import load_table_replay_binding
from .svg_rasterization import MAX_INPUT_BYTES


_ARCHIVE_SCHEMA = "autodata:retained-svg-input:v1"
_SVG_MEDIA = "image/svg+xml"
_BINARY_RESOURCE_KINDS = {"asset", "binary"}
_MAX_ENVELOPE_BYTES = 4 * ((MAX_INPUT_BYTES + 2) // 3) + 8192


def _archive_identity(binding):
    return {
        "article_id": str(binding.canonical_article_id),
        "source_revision_id": str(binding.source_revision_id),
        "source_observation_id": str(binding.source_observation_id),
        "source_fingerprint": binding.source_fingerprint,
        "provider": binding.context.key.provider,
    }


def _missing_svg_refs(binding):
    assets = [entry for entry in binding.row["resource_manifest"][1:]
              if entry.get("role") == "asset" and entry.get("failure_code") == "UNSUPPORTED_ASSET_MEDIA"]
    if not 0 < len(assets) < _MAX_RESOURCES:
        raise ValueError("SOURCE_SVG_ARCHIVE_UNSUPPORTED")
    refs = [asset["opaque_ref"] for asset in assets]
    if len(set(refs)) != len(refs):
        raise ValueError("SOURCE_SVG_ARCHIVE_AMBIGUOUS")
    return refs


def _write_json(directory, name, value):
    descriptor = os.open(
        directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True)


def stage_svg_archive(repo, article_id, source_revision_id, *, registry, destination):
    """Read only referenced assets from the retained article's configured provider."""
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        binding = load_table_replay_binding(cur, source_revision_id)
        current = cur.execute(
            "SELECT current_source_revision_id FROM canonical_articles WHERE canonical_article_id=%s",
            (article_id,),
        ).fetchone()
    if (binding.canonical_article_id != article_id
            or current is None or current["current_source_revision_id"] != source_revision_id):
        raise ValueError("SOURCE_SVG_ARCHIVE_ARTICLE_MISMATCH")
    refs = _missing_svg_refs(binding)
    provider = binding.context.key.provider
    client = registry.get(provider)
    if client is None or client.provider != provider:
        raise ValueError("SOURCE_SVG_ARCHIVE_PROVIDER_REQUIRED")
    destination = Path(destination).absolute()
    _private_path(destination.parent, directory=True)
    _outside_git(destination)
    destination.mkdir(mode=0o700)
    resources = []
    total_size = 0
    try:
        for index, ref in enumerate(refs):
            envelope = client.read_resource(ref, timeout=6)
            payload = envelope.to_source_resource().payload
            total_size += len(payload)
            if (envelope.provider != provider or envelope.body.get("kind") not in _BINARY_RESOURCE_KINDS
                    or envelope.body.get("media_type") != _SVG_MEDIA
                    or not 0 < len(payload) <= MAX_INPUT_BYTES or total_size > _MAX_TOTAL_BYTES):
                raise ValueError("SOURCE_SVG_ARCHIVE_RESOURCE_INVALID")
            body = {
                "request_id": envelope.request_id, "provider": provider,
                "source_revision": envelope.source_revision, "fetched_at": envelope.fetched_at,
                "source_locator": envelope.source_locator or envelope.resource_uri,
                "kind": envelope.body["kind"], "media_type": _SVG_MEDIA,
                "sha256": envelope.body["sha256"], "content_base64": b64encode(payload).decode("ascii"),
            }
            _validated_envelope(body, "resource", provider, None, "")
            _write_json(destination, f"asset-{index:02d}.json", body)
            resources.append({"ref": ref, "sha256": body["sha256"]})
        _write_json(destination, "archive.json", {
            "schema": _ARCHIVE_SCHEMA, "identity": _archive_identity(binding), "resources": resources,
        })
    except BaseException:
        for path in destination.iterdir():
            path.unlink()
        destination.rmdir()
        raise
    return {"status": "prepared", "article_id": str(article_id), "asset_count": len(resources)}


def read_svg_archive(repo, source_revision_id, directory):
    """Bind approved local input bytes to their original retained observation."""
    directory = _private_path(directory, directory=True)
    archive = _read_private_json(directory / "archive.json")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        binding = load_table_replay_binding(cur, source_revision_id)
    refs = _missing_svg_refs(binding)
    if (not isinstance(archive, dict) or set(archive) != {"schema", "identity", "resources"}
            or archive["schema"] != _ARCHIVE_SCHEMA or archive["identity"] != _archive_identity(binding)
            or not isinstance(archive["resources"], list) or len(archive["resources"]) != len(refs)):
        raise ValueError("SOURCE_SVG_ARCHIVE_BINDING_MISMATCH")
    provider = binding.context.key.provider
    assets = {}
    total_size = 0
    for index, (ref, resource) in enumerate(zip(refs, archive["resources"], strict=True)):
        body = _read_private_json(directory / f"asset-{index:02d}.json", limit=_MAX_ENVELOPE_BYTES)
        envelope = _validated_envelope(body, "resource", provider, None, "")
        payload = envelope.to_source_resource().payload
        total_size += len(payload)
        if (resource != {"ref": ref, "sha256": body.get("sha256")}
                or body.get("kind") not in _BINARY_RESOURCE_KINDS or body.get("media_type") != _SVG_MEDIA
                or not 0 < len(payload) <= MAX_INPUT_BYTES or total_size > _MAX_TOTAL_BYTES):
            raise ValueError("SOURCE_SVG_ARCHIVE_RESOURCE_INVALID")
        assets[ref] = envelope
    return binding, assets
