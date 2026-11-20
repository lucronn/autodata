#!/usr/bin/env python3
"""Authored-only Docker validator smoke; requires exact-package root approval.

Imports authored unit fixture only. No transport/DB/S3/service access exists.
"""
import importlib.util
import json
from pathlib import Path
import sys
import uuid


def main():
    root = Path(__file__).absolute().parent
    spec = importlib.util.spec_from_file_location('authored_test', root / 'test_retained_article_integrity.py')
    authored = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(authored)
    m = authored.m
    if len(sys.argv) != 2:
        raise SystemExit('Expected reviewed script SHA256')
    expected = sys.argv[1]
    script = root / 'retained_article_integrity.py'
    source, seal = m.script_guard(script, expected)
    value = authored.fixture()
    expected_receipt = m.receipt_guard(m.validate(m.encoded(value)))
    name = 'autodata-retained-authored-' + uuid.uuid4().hex
    try:
        result = m.bounded_run(m.validator_command(script, name), input=m.encoded(value),
                               timeout=10, stdout_max=4096)
        m.require(result.returncode == 0, 'AUTHORED_VALIDATOR_FAILED')
        receipt = m.receipt_guard(json.loads(result.stdout))
        m.require(receipt == expected_receipt, 'AUTHORED_VALIDATOR_FAILED')
        m.require(m.script_guard(script, expected) == (source, seal), 'SCRIPT_SEAL')
        print(json.dumps({'authored_only': True, 'passed': True, 'script_seal_verified': True,
                          'strict_receipt_verified': True, 'real_db_s3_access': False}))
        return 0
    except BaseException:
        print(json.dumps({'authored_only': True, 'passed': False, 'code': 'AUTHORED_VALIDATOR_FAILED'}))
        return 1
    finally:
        m.bounded_run([*m.DOCKER, 'rm', '-f', name], timeout=5, stdout_max=1024)


if __name__ == '__main__':
    raise SystemExit(main())
