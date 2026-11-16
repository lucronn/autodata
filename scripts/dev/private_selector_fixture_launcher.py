"""Fixed physical one-shot fixture launcher; default verifies files only."""
import argparse
import json
from pathlib import Path
import private_selector_adapter_contract as c
import private_selector_local_transport as t
import private_selector_image_fixture as f
import fixture_client


def verify(manifest_path, manifest_sha, seal_sha):
    c.require(Path(__file__).resolve() == t.ROOT / 'launch_reviewed_fixture.py', 'fixture_launcher_path')
    c.require(Path(manifest_path) == t.ROOT / 'fixture-manifest.json', 'fixture_manifest_path')
    for module, name in ((c, 'private_selector_adapter_contract.py'),
                         (t, 'private_selector_local_transport.py'),
                         (f, 'private_selector_image_fixture.py'), (fixture_client, 'fixture_client.py')):
        c.require(Path(module.__file__).resolve() == t.ROOT / name, 'fixture_import_path')
    c.require(c.full_id(manifest_sha) and t.file_hash(manifest_path) == manifest_sha, 'fixture_manifest_hash')
    manifest = t.private_json(manifest_path)
    c.validate(manifest, 'fixture')
    seal_path = t.ROOT / 'transport-execution-seal.json'
    c.require(c.full_id(seal_sha) and t.file_hash(seal_path) == seal_sha, 'fixture_external_seal_hash')
    seal = t.private_json(seal_path)
    c.require(seal.get('manifest_sha256') == c.digest(manifest)
              and seal.get('artifacts') == manifest['artifacts'], 'fixture_manifest_seal')
    c.require(seal.get('external_launcher_sha256') == t.file_hash(t.ROOT / 'launch_reviewed_fixture.py'),
              'fixture_launcher_seal')
    # paths() is a pure mapping: do not construct a live backend for metadata validation.
    names = {'archive': t.PACKAGE / 'source.tar', 'source_inventory': t.PACKAGE / 'manifest.json',
             'contract': t.ROOT / 'private_selector_adapter_contract.py',
             'transport': t.ROOT / 'private_selector_local_transport.py',
             'fixture_adapter': t.ROOT / 'private_selector_image_fixture.py',
             'fixture_bootstrap': t.ROOT / 'fixture_bootstrap.py', 'fixture_client': t.ROOT / 'fixture_client.py',
             'fixture_plan': t.ROOT / 'fixture-plan.json',
             'fixture_payload_bootstrap': t.ROOT / 'fixture-bootstrap.create.json',
             'fixture_payload_worker': t.ROOT / 'fixture-worker.create.json'}
    for key, path in names.items():
        c.require(t.file_hash(path) == manifest['artifacts'][key], 'fixture_artifact_hash')
    t.verify_inventory(t.PACKAGE, manifest['artifacts']['source_inventory'], c.SOURCE, c.TREE)
    return manifest


def launch(manifest, seal_sha, *, execute=False):
    if not execute:
        return {'status': 'PHYSICAL_FIXTURE_VERIFIED_EXECUTION_HELD',
                'manifest_sha256': c.digest(manifest), 'live_backend_constructed': False}
    c.require(manifest.get('execution_approved') is True, 'fixture_phase_unapproved')
    # The host wrapper composes independently checked image/source/security proofs with behavior checks.
    backend = fixture_client.wrap_transport(t.LocalTransport)(manifest, external_seal_sha=seal_sha,
                                                              dispatch_enabled=True)
    try:
        return f.Fixture(manifest, backend).run()
    finally:
        backend.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True); p.add_argument('--approved-manifest-sha', required=True)
    p.add_argument('--external-seal-sha', required=True); p.add_argument('--execute', action='store_true')
    args = p.parse_args(argv)
    manifest = verify(args.manifest, args.approved_manifest_sha, args.external_seal_sha)
    print(json.dumps(launch(manifest, args.external_seal_sha, execute=args.execute), sort_keys=True))


if __name__ == '__main__': main()
