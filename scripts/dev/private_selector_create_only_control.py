"""Root-reviewed CREATE/inspect/remove lifecycle probe; never START or exec."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import private_selector_adapter_contract as c
import private_selector_local_transport as t


def owned_created(raw, payload, name):
    c.require(c.full_id(raw.get('Id')) and raw.get('Name') == '/' + name
              and raw.get('Image') == payload['Image'], 'create_identity_unknown')
    for key in ('Cmd', 'Entrypoint', 'User', 'WorkingDir'):
        c.require(c.typed_equal(raw['Config'].get(key), payload.get(key)), 'create_config_unknown')
    c.require(dict(x.split('=', 1) for x in raw['Config']['Env'])
              == dict(x.split('=', 1) for x in payload['Env']), 'create_environment_unknown')
    for key, expected in payload['HostConfig'].items():
        if key == 'RestartPolicy': expected = {'Name': 'no', 'MaximumRetryCount': 0}
        c.require(c.typed_equal(raw['HostConfig'].get(key), expected), 'create_hostconfig_unknown')
    mounts = raw['Mounts']; expected = payload['HostConfig']['Mounts'][0]
    c.require(len(mounts) == 1 and mounts[0]['Source'] == expected['Source']
              and mounts[0]['Destination'] == '/app' and mounts[0]['RW'] is False,
              'create_mounts_unknown')
    state = raw['State']
    c.require(state['Status'] == 'created' and state['Running'] is False
              and state['Restarting'] is False and state['Pid'] == 0
              and state['StartedAt'] == '0001-01-01T00:00:00Z'
              and raw['RestartCount'] == 0, 'create_never_started_unknown')


def run(control, backend):
    """Backend injection makes error/response ordering tests fully offline."""
    results = []
    c.require([x['role'] for x in control['commands']] == ['bootstrap', 'worker'], 'create_roles')
    for command in control['commands']:
        role = command['role']; name = command['owned_name']
        backend.boundary(command)
        c.require(backend.absent_name(name), 'create_name_exists')
        response = backend.create(command)
        # Persist even malformed/uncertain response BEFORE parsing or validating an ID.
        backend.record('create-response-' + role, {'response': response.decode('utf-8', errors='replace')})
        value = json.loads(response)
        identifier = value.get('Id')
        c.require(c.full_id(identifier), 'create_id_unknown')
        backend.record('create-returned-id-' + role, {'id': identifier})
        raw = backend.inspect(identifier)
        backend.record('create-full-identity-' + role, raw)
        owned_created(raw, command['payload'], name)
        # Recheck the entire immutable identity and never-running state immediately before removal.
        backend.boundary(command)
        c.require(backend.inspect(identifier) == raw, 'create_identity_changed')
        backend.remove(identifier)
        c.require(backend.absent(identifier), 'create_cleanup_unknown')
        result = {'role': role, 'id': identifier, 'created_hostconfig_sha256': c.digest(raw['HostConfig']),
                  'never_started': True, 'removed_absent': True}
        backend.record('create-cleaned-' + role, result); results.append(result)
    receipt = {'status': 'CREATE_ONLY_PASS_REMOVED_ABSENT', 'results': results,
               'starts': 0, 'exec_sql_product_http_provider_calls': 0}
    backend.record('create-only-result', receipt)
    return receipt


class Local:
    def __init__(self, control, output):
        self.control, self.output = control, Path(output)
    def docker(self, *args):
        return t.bounded(['/usr/bin/docker', '--config', str(t.ROOT / 'docker-config'),
                          '--host', 'unix:///var/run/docker.sock', *args], timeout=15, limit=262144)
    def boundary(self, command):
        import os, stat
        state = t.SOCKET.stat()
        c.require(stat.S_ISSOCK(state.st_mode) and (state.st_dev, state.st_ino) == t.SOCKET_ID
                  and t.SOCKET.resolve() == t.SOCKET_REAL, 'create_socket')
        c.require(not list((t.ROOT / 'docker-config').iterdir()), 'create_docker_config')
        c.require(self.docker('info', '--format', '{{.DockerRootDir}}').decode().strip() == t.DOCKER_ROOT,
                  'create_docker_root')
        c.require(os.statvfs('/home/corp').f_bavail * os.statvfs('/home/corp').f_frsize >= 5502926848,
                  'create_home_capacity')
        c.require(os.statvfs(t.DOCKER_ROOT).f_bavail * os.statvfs(t.DOCKER_ROOT).f_frsize >= 947912704,
                  'create_docker_capacity')
        payload_path = Path(command['payload_path'])
        c.require(payload_path.parent == t.ROOT and payload_path.resolve() == payload_path,
                  'create_payload_path')
        c.require(hashlib.sha256(payload_path.read_bytes()).hexdigest() == command['payload_sha256']
                  and json.loads(payload_path.read_text()) == command['payload'], 'create_payload_hash')
        network = self.control['network']
        raw = json.loads(self.docker('network', 'inspect', network['id']))[0]
        c.require(raw['Internal'] is True and set(raw.get('Containers', {})) == set(network['peer_identities']),
                  'create_network')
        for identifier, expected in network['peer_identities'].items():
            value = self.inspect(identifier)
            c.require(c.digest({k: value[k] for k in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')})
                      == expected, 'create_peer_identity')
        value = self.inspect(c.OLD)
        c.require(value['State']['Running'] is True and value['State']['Pid'] == 1552737
                  and value['RestartCount'] == 0 and value['Image'] == c.IMAGE
                  and c.digest(value['Config']) == c.OLD_IDENTITY['config']
                  and c.digest(value['Mounts']) == c.OLD_IDENTITY['mounts']
                  and c.digest(value['HostConfig']) == c.OLD_IDENTITY['hostconfig_by_status']['running'],
                  'create_serving_identity')
    def absent_name(self, name):
        return not self.docker('ps', '-aq', '--no-trunc', '--filter', 'name=^/' + name + '$').strip()
    def absent(self, identifier):
        c.require(c.full_id(identifier), 'create_cleanup_id')
        return not self.docker('ps', '-aq', '--no-trunc', '--filter', 'id=' + identifier).strip()
    def inspect(self, identifier):
        c.require(c.full_id(identifier), 'create_inspect_id')
        rows = json.loads(self.docker('inspect', identifier))
        c.require(len(rows) == 1 and rows[0]['Id'] == identifier, 'create_inspect_unknown')
        return rows[0]
    def create(self, command):
        return t.bounded(command['argv'], timeout=8, limit=65536)
    def remove(self, identifier):
        c.require(c.full_id(identifier), 'create_cleanup_id')
        self.docker('rm', identifier)
    def record(self, name, value):
        import os
        c.require(re.fullmatch('[a-z-]+', name) is not None, 'create_receipt_name')
        fd = os.open(self.output / (name + '.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(self.output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--control', required=True); p.add_argument('--approved-sha', required=True)
    p.add_argument('--output', required=True); p.add_argument('--execute', action='store_true')
    args = p.parse_args(); path = Path(args.control); data = path.read_bytes()
    c.require(hashlib.sha256(data).hexdigest() == args.approved_sha and c.full_id(args.approved_sha), 'create_control_hash')
    control = json.loads(data)
    for command in control['commands']:
        role = command['role']; name = command['owned_name']; payload = command['payload']
        c.require(role in ('bootstrap', 'worker') and re.fullmatch('autodata-selector-fixture-[a-f0-9]{32}-' + role + '-lifecycle', name), 'create_name')
        expected = ['/usr/bin/curl', '--disable', '--unix-socket', '/var/run/docker.sock', '--noproxy', '*',
                    '--max-time', '5', '--silent', '--show-error', '--fail-with-body', '--header',
                    'Content-Type: application/json', '--data-binary', '@' + command['payload_path'],
                    'http://localhost/v1.43/containers/create?name=' + name]
        c.require(command['argv'] == expected and payload['Image'] == (c.TEST_IMAGE if role == 'bootstrap' else c.IMAGE)
                  and payload['HostConfig']['NetworkMode'] == control['network']['id'], 'create_command')
    if not args.execute:
        print(json.dumps({'status': 'CREATE_ONLY_CONTROL_VALID_EXECUTION_HELD'})); return
    output = Path(args.output)
    c.require(output.parent == t.EVIDENCE and output.parent.resolve() == t.EVIDENCE,
              'create_output_path')
    output.mkdir(mode=0o700)  # Each approval has a new output root; never replay old markers.
    print(json.dumps(run(control, Local(control, output)), sort_keys=True))


if __name__ == '__main__': main()
