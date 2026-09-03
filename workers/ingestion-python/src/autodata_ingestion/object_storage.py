"""Provider-neutral object-storage setup helpers."""

from __future__ import annotations

from typing import Any


def ensure_versioned_bucket(
    client: Any,
    bucket: str,
    versioning_config_factory: Any | None = None,
) -> dict[str, Any]:
    """Create a bucket if needed and require object versioning for its artifacts."""

    bucket = bucket.strip()
    if not bucket:
        raise ValueError("object-storage bucket is required")
    created = not client.bucket_exists(bucket)
    if created:
        client.make_bucket(bucket)

    current = client.get_bucket_versioning(bucket)
    status = current if isinstance(current, str) else getattr(current, "status", None)
    if status != "Enabled":
        if versioning_config_factory is None:
            from minio.versioningconfig import VersioningConfig

            versioning_config_factory = VersioningConfig
        client.set_bucket_versioning(bucket, versioning_config_factory("Enabled"))
        status = "Enabled"
    return {"bucket": bucket, "created": created, "versioning": status}
