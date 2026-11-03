#!/usr/bin/env python3
"""Measure the explicitly synthetic R0 regression facts; never staging evidence."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def pointer(value, path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("invalid pointer")
    for part in path[1:].split("/"):
        if re.search(r"~(?![01])", part):
            raise ValueError("invalid pointer escape")
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", required=True, type=Path)
    args = parser.parse_args()
    population = json.loads(args.population.read_bytes())
    subject = os.environ["AUTODATA_SUBJECT_SHA"]
    root = Path(os.environ["AUTODATA_EVIDENCE_ROOT"])
    if (
        not re.fullmatch("[0-9a-f]{40}", subject)
        or population["scope"] != "synthetic-regression"
    ):
        raise ValueError("invalid fixture context")
    eligible = sorted(rec["fact_id"] for rec in population["records"])
    proofs = []
    uncovered = []
    if len(eligible) != len(set(eligible)):
        raise ValueError("duplicate eligible ID")
    for rec in population["records"]:
        try:
            data = []
            for key in ("source_ref", "extraction_ref"):
                ref = rec[key]
                if (
                    not isinstance(ref, str)
                    or "\\" in ref
                    or any(x in ("", "..", ".") for x in ref.split("/"))
                    or ref.startswith("/")
                ):
                    raise ValueError("unsafe fixture ref")
                data.append((args.population.parent / ref).read_bytes())
            source, extraction = data
            a = pointer(json.loads(source), rec["source_pointer"])
            b = pointer(json.loads(extraction), rec["extraction_pointer"])
            if canonical(a) != canonical(b):
                raise ValueError("source/extraction mismatch")
            proofs.append(
                {
                    "fact_id": rec["fact_id"],
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "extraction_sha256": hashlib.sha256(extraction).hexdigest(),
                    "source_pointer": rec["source_pointer"],
                    "extraction_pointer": rec["extraction_pointer"],
                    "value_sha256": hashlib.sha256(canonical(a)).hexdigest(),
                }
            )
        except (KeyError, ValueError, IndexError, OSError) as error:
            uncovered.append({"fact_id": rec["fact_id"], "reason": str(error)})
    report = {
        "schema_version": 2,
        "subject_sha": subject,
        "population_id": population["population_id"],
        "scope": "synthetic-regression",
        "population_sha256": hashlib.sha256(canonical(population)).hexdigest(),
        "eligible_ids": eligible,
        "covered_ids": sorted(p["fact_id"] for p in proofs),
        "uncovered": uncovered,
        "records": proofs,
    }
    root.mkdir(parents=True, exist_ok=True)
    with (root / "provenance.json").open("x") as output:
        json.dump(report, output, sort_keys=True)
        output.write("\n")
    return 0 if eligible and not uncovered else 1


if __name__ == "__main__":
    raise SystemExit(main())
