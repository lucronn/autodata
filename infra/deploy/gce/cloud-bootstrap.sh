#!/bin/sh
# Fixed staging launcher and offline plan renderer; discard ambient credentials.
exec /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I - "$@" <<'PY'
"""Preserved offline plan; apply delegates only to the installed staging helper."""
from datetime import datetime, timezone
import importlib.util
import json
import sys

HOST_CONFIG = '/etc/autodata/host.json'
RUNTIME_HELPER = '/opt/autodata/bin/runtime-check.py'
STAGING_HELPER = '/opt/autodata/bin/staging_bootstrap.py'


def load_runtime():
    spec = importlib.util.spec_from_file_location('bootstrap_runtime_v1', RUNTIME_HELPER)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def load_staging():
    spec = importlib.util.spec_from_file_location('staging_bootstrap_v1', STAGING_HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_plan(config, runtime):
    config_hash = runtime.validate_config(config)
    resources = config['resources']
    host, backup, firebase = resources['host_project_id'], resources['backup_project_id'], config['firebase']['project_id']
    apis = {}
    for project, names in ((host, ['compute.googleapis.com', 'artifactregistry.googleapis.com', 'iam.googleapis.com',
                                   'iamcredentials.googleapis.com', 'sts.googleapis.com', 'iap.googleapis.com',
                                   'oslogin.googleapis.com', 'secretmanager.googleapis.com', 'monitoring.googleapis.com']),
                           (backup, ['compute.googleapis.com', 'storage.googleapis.com']),
                           (firebase, ['identitytoolkit.googleapis.com'])):
        apis.setdefault(project, set()).update(names)
    attached_email = 'autodata-api-firebase@' + host + '.iam.gserviceaccount.com'
    return {
        'schema_version': 1, 'execution_enabled': False, 'service_config_sha256': config_hash,
        'environment': config['environment'], 'public_origin': config['public_origin'],
        'apis': {project: sorted(names) for project, names in sorted(apis.items())},
        'vm': {'project': host, 'zone': resources['zone'], 'name': resources['instance_name'],
               'proposed_machine_type': 'e2-standard-4', 'platform': 'linux/amd64',
               'os_login': True, 'block_project_ssh_keys': True, 'default_service_account': False,
               'boot_image_resolved': False, 'cost_and_region_approved': False},
        'data_disk': {'project': host, 'zone': resources['zone'], 'name': resources['data_disk_name'],
                      'filesystem_uuid': resources['data_disk_filesystem_uuid'],
                      'proposed_size_gib': 200, 'proposed_type': 'pd-balanced', 'mount': '/var/lib/autodata',
                      'format_authorized': False, 'observed_identity_verified': False},
        'static_address': {'project': host, 'region': resources['region'], 'name': resources['static_ip_name']},
        'artifact_repository': {'project': host, 'name': resources['artifact_repository']},
        'backup_bucket': {'project': backup, 'name': resources['backup_bucket'],
                          'location': resources['region'], 'uniform_bucket_level_access': True,
                          'public_access_prevention': 'enforced', 'routine_delete_authority': False,
                          'retention_policy_approved': False},
        'attached_identity': {'email': attached_email, 'permission_project': firebase,
                              'permissions': ['firebaseauth.users.get'],
                              'access_scopes': ['https://www.googleapis.com/auth/cloud-platform',
                                                'https://www.googleapis.com/auth/userinfo.email',
                                                'https://www.googleapis.com/auth/identitytoolkit'],
                              'uid_restriction_supported': False, 'other_roles': []},
        'external_authorities': {
            'publish': {'host_administrator': False, 'registry': 'writer for configured repository',
                        'secrets': False, 'backup': False},
            'deploy': {'host_administrator': True, 'registry': 'reader for configured repository',
                       'secrets': 'only manifest-bound numeric versions of named secrets',
                       'iap_os_login': 'trusted administrator for configured VM only'},
            'backup': {'host_administrator': False, 'delete_authority': False, 'secrets': False,
                       'iap_os_login': 'non-admin for configured VM only',
                       'privileged_helpers': ['/opt/autodata/bin/backup-host.sh begin|status|export|resume UUID'],
                       'disk_permissions': ['compute.disks.get', 'compute.disks.createSnapshot'],
                       'snapshot_permissions': ['compute.snapshots.create', 'compute.snapshots.get',
                                                'compute.snapshots.list', 'compute.globalOperations.get'],
                       'snapshot_scope': 'configured disk and owned UUID snapshot prefix; project-level exceptions require review',
                       'bucket_permissions': ['storage.objects.create']},
            'monitor': {'host_administrator': False, 'secrets': False, 'backup': False, 'registry': False,
                        'iap_os_login': 'non-admin for configured VM only',
                        'privileged_helpers': ['/opt/autodata/bin/runtime-check.py metrics --release SHA'],
                        'monitoring_role': 'roles/monitoring.metricWriter'},
            'restore': {'separately_authorized': True, 'binding_resolved': False,
                        'authority': 'isolated restore only; backup read and host administration require separate approval'}},
        'wif_requirements': {'binding_resolved': False,
                             'exact_claims': ['repository', 'repository_id', 'repository_owner_id', 'environment', 'ref', 'workflow_ref'],
                             'environment': config['environment'], 'protected_environment_required': True,
                             'workflows': {'publish': 'release-workshop.yml', 'deploy': 'release-workshop.yml',
                                           'backup': 'backup-workshop.yml', 'monitor': 'monitor-workshop.yml'},
                             'service_account_keys_allowed': False, 'token_creator_on_attached_identity': False},
        'ingress': [{'ports': [80, 443], 'source_ipv4': '0.0.0.0/0', 'target_instance': resources['instance_name']},
                    {'ports': [22], 'source_ipv4': '35.235.240.0/20', 'target_instance': resources['instance_name']}],
        'host_guards': {'verified': False, 'api_metadata_address': '172.30.10.10', 'api_metadata_bridge': 'br-ad-edge',
                        'metadata_ipv4': '169.254.169.254', 'metadata_ipv6': 'fd20:ce::254',
                        'trusted_host_metadata_uid': 0, 'storage_address': '172.30.20.40',
                        'storage_allowed_tcp_ports': [9000], 'ipv6_enabled': False,
                        'route_overlap_checked': False, 'requires_bridge_and_routed_storage_guard': True},
        'unresolved_inputs': ['owner project/billing/cost/region/residency approval',
                              'reviewed VPC selection and route overlap evidence',
                              'reviewed immutable boot image and Docker/Compose/gcloud package pins',
                              'numeric repository and owner IDs, exact ref, external principal IDs and WIF bindings',
                              'protected environment rules and separate deployment authorization',
                              'per-resource IAM conditions and unavoidable project-level snapshot permissions',
                              'observed new/empty disk identity and approved format/mount operation',
                              'backup retention policy, restore operator, RPO/RTO and maintenance acceptance',
                              'owner alert destination, native uptime/Compute and missing-heartbeat alert policy',
                              'real metadata/storage denial, Firebase SDK refresh, OS Login and reboot evidence',
                              'licensed providers, actual origin/Firebase/TLS approval and separately approved cutover']}


def receipt(status, failure_code=None, plan=None, operation='plan'):
    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    value = {'schema_version': 1, 'operation': 'cloud-bootstrap.sh ' + operation, 'run_id': None, 'source_sha': None,
             'status': status, 'started_at': now, 'finished_at': now, 'checks': {},
             'failure_code': failure_code, 'definition_only': True}
    if plan is not None:
        value.update(plan=plan, checks={'config': True})
    return value


def main(argv, runtime=None):
    if type(argv) not in (list, tuple) or not all(type(arg) is str for arg in argv) or list(argv) not in ([], ['plan'], ['apply']):
        return 2, receipt('failed', 'invalid_input')
    if list(argv) == ['apply']:
        try:
            helper = load_staging()
            runtime = runtime if runtime is not None else load_runtime()
            return helper.main(runtime)
        except Exception:
            return 3, receipt('failed', 'missing_dependency', operation='apply')
    try:
        runtime = runtime if runtime is not None else load_runtime()
    except Exception:
        return 3, receipt('failed', 'missing_dependency')
    try:
        config = runtime.read_private_json(HOST_CONFIG)
    except Exception:
        return 3, receipt('failed', 'missing_dependency')
    try:
        plan = build_plan(config, runtime)
        result = receipt('passed', plan=plan)
        runtime.require(len(runtime.canonical_bytes(result)) <= 65536)
        return 0, result
    except runtime.ContractError:
        return 2, receipt('failed', 'invalid_input')
    except Exception:
        return 3, receipt('failed', 'missing_dependency')


if __name__ == '__main__':
    code, output = main(sys.argv[1:])
    sys.stdout.write(json.dumps(output, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')
    raise SystemExit(code)
PY
