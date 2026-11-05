#!/usr/bin/env python3
"""Run mandatory isolated lifecycle acceptance and retain measured evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "test_article_lifecycle_schema.py", "test_source_job_persistence.py",
    "test_article_source_persistence.py", "test_article_transform.py",
    "test_article_publication.py", "test_article_worker.py",
    "test_article_lifecycle_integration.py", "test_article_document.py",
    "test_procedure_rewrite.py", "test_mercury2.py",
    "test_catalog_service.py", "test_http_service.py",
)


def junit_measurements(path):
    root = ET.parse(path).getroot()
    tests = list(root.iter("testcase"))
    return {"tests": len(tests), "failures": sum(t.find("failure") is not None for t in tests),
            "errors": sum(t.find("error") is not None for t in tests),
            "skipped": sum(t.find("skipped") is not None for t in tests),
            "test_ids": [t.get("classname", "") + "." + t.get("name", "") for t in tests]}


def candidate_identity(supplied):
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5, check=True)
        sha = result.stdout.strip()
        if supplied and supplied != sha:
            raise ValueError("candidate SHA differs from checkout")
        return {"sha": sha, "source": "git rev-parse HEAD in runner"}
    except (OSError, subprocess.SubprocessError):
        if not supplied or not re.fullmatch(r"[a-f0-9]{40}", supplied):
            raise ValueError("read-only container needs --candidate-sha from host git rev-parse HEAD")
        return {"sha": supplied, "source": "host-supplied git rev-parse HEAD; runner has no readable git metadata"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["fixture"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha")
    args = parser.parse_args(argv)
    if os.environ.get("AUTODATA_LIFECYCLE_TEST") != "1":
        parser.error("isolated lifecycle Compose runner required")
    for name in ("BANKONE_BASE_URL", "BANKTWO_BASE_URL", "INCEPTION_API_BASE_URL", "INCEPTION_API_KEY"):
        if os.environ.get(name):
            parser.error("fixture runner must not inherit source/model configuration: " + name)
    identity = candidate_identity(args.candidate_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    junit = args.output.with_suffix(".xml")
    log = args.output.with_suffix(".log")
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=" + str(junit)]
    command += ["workers/ingestion-python/tests/" + name for name in REQUIRED]
    command += ["scripts/dev/test_backfill_article_lifecycle.py", "scripts/dev/test_article_lifecycle_smoke.py",
                "workers/enrichment-python/tests/test_outbox.py", "scripts/contracts/test_contracts.py"]
    started = datetime.now(timezone.utc).isoformat()
    start_ns = time.time_ns()
    with log.open("w") as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False)
    measured = junit_measurements(junit) if junit.exists() else {"tests": 0, "failures": 0, "errors": 1, "skipped": 0, "test_ids": []}
    runtime_files = [p for p in args.output.parent.glob("runtime-*.json") if p.stat().st_mtime_ns >= start_ns]
    records = [json.loads(p.read_text()) for p in runtime_files]
    invariants = all(record["expected_invariants"] == record["measured_invariants"] for record in records)
    succeeded = result.returncode == 0 and measured["tests"] > 0 and not any(measured[k] for k in ("failures", "errors", "skipped")) and bool(records) and invariants
    paths = [p for p in (log, junit, *runtime_files) if p.exists()]
    payload = {"candidate": identity, "mode": "fixture", "fixture_project": "autodata-r2-lifecycle", "argv": command,
               "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "exit_status": result.returncode,
               "expected": {"failures": 0, "errors": 0, "skipped": 0, "runtime_evidence_required": True, "invariants_match": True},
               "measured": measured, "runtime_evidence_count": len(records), "invariants_match": invariants, "passed": succeeded,
               "runtime_evidence": records,
               "artifacts": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"passed": succeeded, "tests": measured["tests"], "evidence": str(args.output)}))
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
