"""Disconnected disposable PG17 protocol. No CLI, socket, subprocess or runtime hook.

Transport implementations own bounded I/O, a single connection and verified close.
Nothing in this module grants maintenance rights or changes production readiness.
"""
import json
import re
import time


class ProbeUnavailable(ValueError):
    def __init__(self):
        super().__init__('schema probe unavailable')


class ProbeTimedOut(ProbeUnavailable):
    def __init__(self):
        ValueError.__init__(self, 'schema probe timed out')


MAX_FRAME = 524288
MAX_WRITE = 65536
MAX_OUTBOUND = 262144
DEADLINE_SECONDS = 12
VERSION = re.compile(r'[0-9]{3}_[a-z0-9_]{1,120}', re.ASCII)
PGOPTIONS = ('-c default_transaction_read_only=on -c statement_timeout=2000 '
             '-c lock_timeout=1000 -c idle_in_transaction_session_timeout=5000 '
             '-c search_path=pg_catalog -c jit=off')
BEGIN_SQL = (b'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n'
             b'LOCK TABLE ONLY public.schema_migrations IN SHARE ROW EXCLUSIVE MODE;\n')
ROLLBACK_SQL = b'ROLLBACK;\n'
TERMINAL = b'AUTODATA_SCHEMA_PROBE_CLOSED_V3\n'
FINISH_SQL = ROLLBACK_SQL + b'\\echo AUTODATA_SCHEMA_PROBE_CLOSED_V3\n\\quit\n'

# Only trusted built-in catalogs occur in relation references. This SQL never
# opens/plans the application table. The fixed PG17 text_ops inventory is 8
# support entries plus 20 comparison operators (REL_17_STABLE catalog data).
CATALOG_SQL = r'''WITH
r AS MATERIALIZED (SELECT * FROM pg_catalog.pg_roles WHERE rolname OPERATOR(pg_catalog.=) 'autodata_schema_probe'),
d AS MATERIALIZED (SELECT * FROM pg_catalog.pg_database WHERE datname OPERATOR(pg_catalog.=) 'autodata'),
n AS MATERIALIZED (SELECT * FROM pg_catalog.pg_namespace WHERE nspname OPERATOR(pg_catalog.=) 'public'),
c AS MATERIALIZED (SELECT c.* FROM pg_catalog.pg_class c JOIN n ON c.relnamespace OPERATOR(pg_catalog.=) n.oid
 WHERE c.relname OPERATOR(pg_catalog.=) 'schema_migrations'),
a AS MATERIALIZED (SELECT a.* FROM pg_catalog.pg_attribute a JOIN c ON a.attrelid OPERATOR(pg_catalog.=) c.oid
 WHERE a.attnum OPERATOR(pg_catalog.>) 0 AND NOT a.attisdropped ORDER BY a.attnum LIMIT 3),
x AS MATERIALIZED (SELECT x.*, z.relam FROM pg_catalog.pg_index x JOIN c ON x.indrelid OPERATOR(pg_catalog.=) c.oid
 JOIN pg_catalog.pg_class z ON z.oid OPERATOR(pg_catalog.=) x.indexrelid),
app_ns AS MATERIALIZED (SELECT * FROM pg_catalog.pg_namespace
 WHERE nspname OPERATOR(pg_catalog.<>) 'information_schema' AND nspname OPERATOR(pg_catalog.!~) '^pg_'),
app_rel AS MATERIALIZED (SELECT z.* FROM pg_catalog.pg_class z JOIN app_ns ON z.relnamespace OPERATOR(pg_catalog.=) app_ns.oid),
fam AS MATERIALIZED (SELECT f.* FROM pg_catalog.pg_opfamily f JOIN pg_catalog.pg_namespace s ON s.oid OPERATOR(pg_catalog.=) f.opfnamespace
 WHERE s.nspname OPERATOR(pg_catalog.=) 'pg_catalog' AND f.opfname OPERATOR(pg_catalog.=) 'text_ops'
 AND f.opfmethod OPERATOR(pg_catalog.=) (SELECT oid FROM pg_catalog.pg_am WHERE amname OPERATOR(pg_catalog.=) 'btree')),
ep(l,r,n,p) AS (VALUES
 ('pg_catalog.text'::pg_catalog.regtype,'pg_catalog.text'::pg_catalog.regtype,1,'pg_catalog.bttextcmp'::pg_catalog.regproc),
 ('pg_catalog.text'::pg_catalog.regtype,'pg_catalog.text'::pg_catalog.regtype,2,'pg_catalog.bttextsortsupport'::pg_catalog.regproc),
 ('pg_catalog.text'::pg_catalog.regtype,'pg_catalog.text'::pg_catalog.regtype,4,'pg_catalog.btvarstrequalimage'::pg_catalog.regproc),
 ('pg_catalog.name'::pg_catalog.regtype,'pg_catalog.name'::pg_catalog.regtype,1,'pg_catalog.btnamecmp'::pg_catalog.regproc),
 ('pg_catalog.name'::pg_catalog.regtype,'pg_catalog.name'::pg_catalog.regtype,2,'pg_catalog.btnamesortsupport'::pg_catalog.regproc),
 ('pg_catalog.name'::pg_catalog.regtype,'pg_catalog.name'::pg_catalog.regtype,4,'pg_catalog.btvarstrequalimage'::pg_catalog.regproc),
 ('pg_catalog.name'::pg_catalog.regtype,'pg_catalog.text'::pg_catalog.regtype,1,'pg_catalog.btnametextcmp'::pg_catalog.regproc),
 ('pg_catalog.text'::pg_catalog.regtype,'pg_catalog.name'::pg_catalog.regtype,1,'pg_catalog.bttextnamecmp'::pg_catalog.regproc)),
ap AS MATERIALIZED (SELECT p.amproclefttype l,p.amprocrighttype r,p.amprocnum n,p.amproc p
 FROM pg_catalog.pg_amproc p JOIN fam ON fam.oid OPERATOR(pg_catalog.=) p.amprocfamily),
eo AS MATERIALIZED (SELECT lt.oid l, rt.oid r, v.n, o.oid o
 FROM pg_catalog.pg_type lt CROSS JOIN pg_catalog.pg_type rt
 CROSS JOIN (VALUES ('<',1),('<=',2),('=',3),('>=',4),('>',5)) AS v(op,n)
 JOIN pg_catalog.pg_operator o ON o.oprname::pg_catalog.text OPERATOR(pg_catalog.=) v.op
 JOIN pg_catalog.pg_namespace s ON s.oid OPERATOR(pg_catalog.=) o.oprnamespace
 WHERE lt.oid IN ('pg_catalog.text'::pg_catalog.regtype,'pg_catalog.name'::pg_catalog.regtype)
 AND rt.oid IN ('pg_catalog.text'::pg_catalog.regtype,'pg_catalog.name'::pg_catalog.regtype)
 AND o.oprleft OPERATOR(pg_catalog.=) lt.oid AND o.oprright OPERATOR(pg_catalog.=) rt.oid
 AND s.nspname OPERATOR(pg_catalog.=) 'pg_catalog'),
ao AS MATERIALIZED (SELECT o.amoplefttype l,o.amoprighttype r,o.amopstrategy n,o.amopopr o
 FROM pg_catalog.pg_amop o JOIN fam ON fam.oid OPERATOR(pg_catalog.=) o.amopfamily
 WHERE o.amoppurpose OPERATOR(pg_catalog.=) 's'),
safety AS MATERIALIZED (SELECT
 (SELECT pg_catalog.count(*) FROM ap) OPERATOR(pg_catalog.=) 8
 AND (SELECT pg_catalog.count(*) FROM ao) OPERATOR(pg_catalog.=) 20
 AND NOT EXISTS (SELECT * FROM ap EXCEPT SELECT * FROM ep)
 AND NOT EXISTS (SELECT * FROM ep EXCEPT SELECT * FROM ap)
 AND NOT EXISTS (SELECT * FROM ao EXCEPT SELECT * FROM eo)
 AND NOT EXISTS (SELECT * FROM eo EXCEPT SELECT * FROM ao)
 AND NOT EXISTS (SELECT FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace s ON s.oid OPERATOR(pg_catalog.=) p.pronamespace
 JOIN pg_catalog.pg_language l ON l.oid OPERATOR(pg_catalog.=) p.prolang
 WHERE p.oid IN (SELECT p FROM ep UNION SELECT o.oprcode FROM pg_catalog.pg_operator o JOIN eo ON eo.o OPERATOR(pg_catalog.=) o.oid)
 AND (s.nspname OPERATOR(pg_catalog.<>) 'pg_catalog' OR l.lanname OPERATOR(pg_catalog.<>) 'internal'
 OR p.prosrc OPERATOR(pg_catalog.<>) p.proname::pg_catalog.text)) AS ok),
heap_am AS MATERIALIZED (SELECT oid FROM pg_catalog.pg_am WHERE amname OPERATOR(pg_catalog.=) 'heap'
 AND amtype OPERATOR(pg_catalog.=) 't' AND amhandler OPERATOR(pg_catalog.=) 'pg_catalog.heap_tableam_handler'::pg_catalog.regproc),
btree_am AS MATERIALIZED (SELECT oid FROM pg_catalog.pg_am WHERE amname OPERATOR(pg_catalog.=) 'btree'
 AND amtype OPERATOR(pg_catalog.=) 'i' AND amhandler OPERATOR(pg_catalog.=) 'pg_catalog.bthandler'::pg_catalog.regproc),
coll AS MATERIALIZED (SELECT oid FROM pg_catalog.pg_collation WHERE collnamespace OPERATOR(pg_catalog.=) 'pg_catalog'::pg_catalog.regnamespace
 AND collname IN ('default','C','POSIX') AND collisdeterministic),
idx AS MATERIALIZED (SELECT pg_catalog.json_build_object(
 'count',(SELECT pg_catalog.count(*) FROM x),
 'primary_version_only', x.indisprimary AND x.indnkeyatts OPERATOR(pg_catalog.=) 1 AND x.indnatts OPERATOR(pg_catalog.=) 1
 AND x.indkey[0] OPERATOR(pg_catalog.=) 1 AND EXISTS (SELECT FROM pg_catalog.pg_constraint k
 WHERE k.conrelid OPERATOR(pg_catalog.=) x.indrelid AND k.conindid OPERATOR(pg_catalog.=) x.indexrelid
 AND k.contype OPERATOR(pg_catalog.=) 'p' AND k.conkey OPERATOR(pg_catalog.=) ARRAY[1]::pg_catalog.int2[]),
 'valid',x.indisvalid,'ready',x.indisready,'live',x.indislive,'unique',x.indisunique,'immediate',x.indimmediate,
 'include_count',x.indnatts OPERATOR(pg_catalog.-) x.indnkeyatts,
 'has_expression',x.indexprs IS NOT NULL,'has_predicate',x.indpred IS NOT NULL,'has_exclusion',x.indisexclusion,
 'btree_builtin',x.relam IN (SELECT oid FROM btree_am),
 'text_ops_builtin',EXISTS (SELECT FROM pg_catalog.pg_opclass z JOIN fam ON z.opcfamily OPERATOR(pg_catalog.=) fam.oid
 WHERE z.oid OPERATOR(pg_catalog.=) x.indclass[0] AND z.opcnamespace OPERATOR(pg_catalog.=) 'pg_catalog'::pg_catalog.regnamespace
 AND z.opcname OPERATOR(pg_catalog.=) 'text_ops' AND z.opcintype OPERATOR(pg_catalog.=) 'pg_catalog.text'::pg_catalog.regtype
 AND z.opcmethod IN (SELECT oid FROM btree_am)),
 'collation_safe',x.indcollation[0] IN (SELECT oid FROM coll),
 'support_inventory_count',(SELECT pg_catalog.count(*) FROM ap) OPERATOR(pg_catalog.+) (SELECT pg_catalog.count(*) FROM ao),
 'support_inventory_matches_baseline',(SELECT ok FROM safety)) AS value FROM x LIMIT 1)
SELECT pg_catalog.json_build_object(
 'protocol_version',3,'phase','catalog_locked',
 'identity',pg_catalog.json_build_object('session_user',session_user,'current_user',current_user,
 'database',pg_catalog.current_database(),'server_version_num',pg_catalog.current_setting('server_version_num')::pg_catalog.int4,
 'transaction_read_only',pg_catalog.current_setting('transaction_read_only') OPERATOR(pg_catalog.=) 'on',
 'default_transaction_read_only',pg_catalog.current_setting('default_transaction_read_only') OPERATOR(pg_catalog.=) 'on',
 'isolation',pg_catalog.current_setting('transaction_isolation'),'client_addr',pg_catalog.inet_client_addr(),'client_port',pg_catalog.inet_client_port()),
 'rights',(SELECT pg_catalog.json_build_object(
 'login',r.rolcanlogin,'superuser',r.rolsuper,'create_db',r.rolcreatedb,'create_role',r.rolcreaterole,
 'replication',r.rolreplication,'bypass_rls',r.rolbypassrls,'inherit',r.rolinherit,
 'membership_count',(SELECT pg_catalog.count(*) FROM pg_catalog.pg_auth_members m WHERE m.member OPERATOR(pg_catalog.=) r.oid),
 'connect',pg_catalog.has_database_privilege(r.oid,d.oid,'CONNECT'),
 'schema_usage',(SELECT pg_catalog.has_schema_privilege(r.oid,n.oid,'USAGE') FROM n),
 'ledger_select',(SELECT pg_catalog.has_table_privilege(r.oid,c.oid,'SELECT') FROM c),
 'ledger_maintain',(SELECT pg_catalog.has_table_privilege(r.oid,c.oid,'MAINTAIN') FROM c),
 'other_maintain',EXISTS (SELECT FROM app_rel z WHERE z.relkind IN ('r','p','v','m','f') AND z.oid NOT IN (SELECT oid FROM c)
 AND pg_catalog.has_table_privilege(r.oid,z.oid,'MAINTAIN')),
 'database_create',pg_catalog.has_database_privilege(r.oid,d.oid,'CREATE'),
 'database_temp',pg_catalog.has_database_privilege(r.oid,d.oid,'TEMP'),'database_owner',d.datdba OPERATOR(pg_catalog.=) r.oid,
 'schema_create',EXISTS (SELECT FROM app_ns z WHERE pg_catalog.has_schema_privilege(r.oid,z.oid,'CREATE')),
 'schema_owner',EXISTS (SELECT FROM app_ns z WHERE z.nspowner OPERATOR(pg_catalog.=) r.oid),
 'relation_owner',EXISTS (SELECT FROM app_rel z WHERE z.relkind OPERATOR(pg_catalog.<>) 'S' AND z.relowner OPERATOR(pg_catalog.=) r.oid),
 'sequence_owner',EXISTS (SELECT FROM app_rel z WHERE z.relkind OPERATOR(pg_catalog.=) 'S' AND z.relowner OPERATOR(pg_catalog.=) r.oid),
 'relation_write',EXISTS (SELECT FROM app_rel z CROSS JOIN pg_catalog.unnest(ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) AS p(privilege)
 WHERE CASE WHEN z.relkind IN ('r','p','v','m','f') THEN pg_catalog.has_table_privilege(r.oid,z.oid,p.privilege) ELSE false END),
 'column_write',EXISTS (SELECT FROM app_rel z CROSS JOIN pg_catalog.unnest(ARRAY['INSERT','UPDATE','REFERENCES']) AS p(privilege)
 WHERE CASE WHEN z.relkind IN ('r','p','v','m','f') THEN pg_catalog.has_any_column_privilege(r.oid,z.oid,p.privilege) ELSE false END),
 'sequence_write',EXISTS (SELECT FROM app_rel z WHERE CASE WHEN z.relkind OPERATOR(pg_catalog.=) 'S'
 THEN pg_catalog.has_sequence_privilege(r.oid,z.oid,'USAGE,UPDATE') ELSE false END)) FROM r CROSS JOIN d),
 'relation',(SELECT pg_catalog.json_build_object('oid',c.oid,'schema','public','name',c.relname,'kind',c.relkind,'persistence',c.relpersistence,
 'heap_builtin',c.relam IN (SELECT oid FROM heap_am),'owner',o.rolname,'owner_login',o.rolcanlogin,
 'is_partition',c.relispartition,'has_inheritance',EXISTS (SELECT FROM pg_catalog.pg_inherits i WHERE i.inhrelid OPERATOR(pg_catalog.=) c.oid OR i.inhparent OPERATOR(pg_catalog.=) c.oid),
 'rls',c.relrowsecurity,'force_rls',c.relforcerowsecurity,
 'rule_count',(SELECT pg_catalog.count(*) FROM pg_catalog.pg_rewrite w WHERE w.ev_class OPERATOR(pg_catalog.=) c.oid),
 'trigger_count',(SELECT pg_catalog.count(*) FROM pg_catalog.pg_trigger t WHERE t.tgrelid OPERATOR(pg_catalog.=) c.oid),
 'dropped_user_column_count',(SELECT pg_catalog.count(*) FROM pg_catalog.pg_attribute z WHERE z.attrelid OPERATOR(pg_catalog.=) c.oid AND z.attnum OPERATOR(pg_catalog.>) 0 AND z.attisdropped),
 'toast_builtin_safe',c.reltoastrelid OPERATOR(pg_catalog.=) 0 OR EXISTS (SELECT FROM pg_catalog.pg_class t
 WHERE t.oid OPERATOR(pg_catalog.=) c.reltoastrelid AND t.relkind OPERATOR(pg_catalog.=) 't' AND t.relam IN (SELECT oid FROM heap_am)
 AND (SELECT pg_catalog.count(*) FROM pg_catalog.pg_index ti WHERE ti.indrelid OPERATOR(pg_catalog.=) t.oid) OPERATOR(pg_catalog.=) 1
 AND NOT EXISTS (SELECT FROM pg_catalog.pg_index ti JOIN pg_catalog.pg_class tc ON tc.oid OPERATOR(pg_catalog.=) ti.indexrelid
 WHERE ti.indrelid OPERATOR(pg_catalog.=) t.oid AND (tc.relam NOT IN (SELECT oid FROM btree_am) OR NOT ti.indisvalid OR NOT ti.indisready OR NOT ti.indislive
 OR ti.indexprs IS NOT NULL OR ti.indpred IS NOT NULL OR ti.indnatts OPERATOR(pg_catalog.<>) 2
 OR EXISTS (SELECT FROM pg_catalog.unnest(ti.indclass::pg_catalog.oid[]) oc(oid) LEFT JOIN pg_catalog.pg_opclass op ON op.oid OPERATOR(pg_catalog.=) oc.oid
 WHERE op.oid IS NULL OR op.opcnamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace OR op.opcname NOT IN ('oid_ops','int4_ops'))))))
 FROM c JOIN pg_catalog.pg_roles o ON o.oid OPERATOR(pg_catalog.=) c.relowner),
 'columns',(SELECT pg_catalog.json_agg(pg_catalog.json_build_object('attnum',a.attnum,'name',a.attname,
 'type',CASE WHEN a.atttypid OPERATOR(pg_catalog.=) 'pg_catalog.text'::pg_catalog.regtype THEN 'pg_catalog.text'
 WHEN a.atttypid OPERATOR(pg_catalog.=) 'pg_catalog.timestamptz'::pg_catalog.regtype THEN 'pg_catalog.timestamptz' ELSE 'rejected' END,
 'not_null',a.attnotnull,'generated',a.attgenerated,'identity',a.attidentity,
 'collation_safe',a.attcollation OPERATOR(pg_catalog.=) 0 OR a.attcollation IN (SELECT oid FROM coll)) ORDER BY a.attnum) FROM a),
 'indexes',(SELECT value FROM idx),
 'builtins',pg_catalog.json_build_object('heap_identity_matches',(SELECT pg_catalog.count(*) FROM heap_am) OPERATOR(pg_catalog.=) 1,
 'btree_identity_matches',(SELECT pg_catalog.count(*) FROM btree_am) OPERATOR(pg_catalog.=) 1,
 'text_identity_matches',EXISTS (SELECT FROM pg_catalog.pg_type WHERE oid OPERATOR(pg_catalog.=) 'pg_catalog.text'::pg_catalog.regtype AND typoutput OPERATOR(pg_catalog.=) 'pg_catalog.textout'::pg_catalog.regproc),
 'timestamptz_identity_matches',EXISTS (SELECT FROM pg_catalog.pg_type WHERE oid OPERATOR(pg_catalog.=) 'pg_catalog.timestamptz'::pg_catalog.regtype AND typoutput OPERATOR(pg_catalog.=) 'pg_catalog.timestamptz_out'::pg_catalog.regproc),
 'text_ops_family_matches',(SELECT pg_catalog.count(*) FROM fam) OPERATOR(pg_catalog.=) 1,
 'operators_and_support_match',(SELECT ok FROM safety)))
'''.encode('ascii') + b';\n'

LEDGER_SQL = r'''WITH sample AS MATERIALIZED (
 SELECT version FROM ONLY public.schema_migrations LIMIT 257),
bounded AS MATERIALIZED (SELECT CASE WHEN pg_catalog.octet_length(version) OPERATOR(pg_catalog.<=) 128
 THEN CASE WHEN version COLLATE pg_catalog."C" OPERATOR(pg_catalog.~) '^[0-9]{3}_[a-z0-9_]{1,120}$' THEN version ELSE NULL END ELSE NULL END AS v FROM sample)
SELECT pg_catalog.json_build_object('protocol_version',3,'phase','ledger_locked',
 'count',pg_catalog.count(*),'overflow',pg_catalog.count(*) OPERATOR(pg_catalog.>) 256,
 'invalid',pg_catalog.count(v) OPERATOR(pg_catalog.<>) pg_catalog.count(*),
 'migrations',CASE WHEN pg_catalog.count(*) OPERATOR(pg_catalog.<=) 256
 AND pg_catalog.count(v) OPERATOR(pg_catalog.=) pg_catalog.count(*)
 THEN COALESCE(pg_catalog.json_agg(v ORDER BY v COLLATE pg_catalog."C"),'[]'::pg_catalog.json) ELSE NULL END)
FROM bounded;
'''.encode('ascii')


def _require(condition):
    if not condition:
        raise ProbeUnavailable()


def _exact(value, expected):
    """Check exact literal structure and scalar types without bool/int coercion."""
    _require(type(value) is type(expected))
    if type(expected) is dict:
        _require(value.keys() == expected.keys())
        for key in expected:
            _exact(value[key], expected[key])
    elif type(expected) is list:
        _require(len(value) == len(expected))
        for item, wanted in zip(value, expected):
            _exact(item, wanted)
    else:
        _require(value == expected)


def validate_catalog(value: dict) -> None:
    _require(type(value) is dict)
    # These are the only varying accepted catalog fields. All others are exact
    # frozen facts; missing/unknown values cannot silently become false/true.
    try:
        oid = value['relation']['oid']
        server = value['identity']['server_version_num']
    except (KeyError, TypeError):
        raise ProbeUnavailable() from None
    _require(type(oid) is int and 1 <= oid <= 4294967295)
    _require(type(server) is int and 170000 <= server <= 179999)
    expected = {
        'protocol_version': 3, 'phase': 'catalog_locked',
        'identity': {'session_user': 'autodata_schema_probe', 'current_user': 'autodata_schema_probe',
                     'database': 'autodata', 'server_version_num': server, 'transaction_read_only': True,
                     'default_transaction_read_only': True, 'isolation': 'repeatable read',
                     'client_addr': None, 'client_port': None},
        'rights': {'login': True, 'superuser': False, 'create_db': False, 'create_role': False,
                   'replication': False, 'bypass_rls': False, 'inherit': False, 'membership_count': 0,
                   'connect': True, 'schema_usage': True, 'ledger_select': True, 'ledger_maintain': True,
                   'other_maintain': False, 'database_create': False, 'database_temp': False,
                   'database_owner': False, 'schema_create': False, 'schema_owner': False,
                   'relation_owner': False, 'sequence_owner': False, 'relation_write': False,
                   'column_write': False, 'sequence_write': False},
        'relation': {'oid': oid, 'schema': 'public', 'name': 'schema_migrations', 'kind': 'r',
                     'persistence': 'p', 'heap_builtin': True, 'owner': 'autodata_schema_owner',
                     'owner_login': False, 'is_partition': False, 'has_inheritance': False,
                     'rls': False, 'force_rls': False, 'rule_count': 0, 'trigger_count': 0,
                     'dropped_user_column_count': 0, 'toast_builtin_safe': True},
        'columns': [{'attnum': 1, 'name': 'version', 'type': 'pg_catalog.text', 'not_null': True,
                     'generated': '', 'identity': '', 'collation_safe': True},
                    {'attnum': 2, 'name': 'applied_at', 'type': 'pg_catalog.timestamptz', 'not_null': True,
                     'generated': '', 'identity': '', 'collation_safe': True}],
        'indexes': {'count': 1, 'primary_version_only': True, 'valid': True, 'ready': True,
                    'live': True, 'unique': True, 'immediate': True, 'include_count': 0,
                    'has_expression': False, 'has_predicate': False, 'has_exclusion': False,
                    'btree_builtin': True, 'text_ops_builtin': True, 'collation_safe': True,
                    'support_inventory_count': 28, 'support_inventory_matches_baseline': True},
        'builtins': {'heap_identity_matches': True, 'btree_identity_matches': True,
                     'text_identity_matches': True, 'timestamptz_identity_matches': True,
                     'text_ops_family_matches': True, 'operators_and_support_match': True}}
    _exact(value, expected)


def _decode(data):
    _require(type(data) is bytes and 0 < len(data) <= MAX_FRAME and data.endswith(b'\n'))
    try:
        source = data.decode('utf-8')
        # Scan before json.loads: cap nesting/member/string/numeric tokens without
        # recursive parsing or a regex over attacker-controlled nested strings.
        stack = []
        pos = 0
        while pos < len(source):
            char = source[pos]
            if char == '"':
                start = pos
                pos += 1
                while pos < len(source):
                    if source[pos] == '\\':
                        pos += 2
                    elif source[pos] == '"':
                        break
                    else:
                        pos += 1
                    _require(pos - start <= 770)
                _require(pos < len(source))
                token = json.loads(source[start:pos + 1])
                _require(type(token) is str and token.isascii() and len(token) <= 128)
            elif char in '[{':
                stack.append([char, 0]); _require(len(stack) <= 8)
            elif char in ']}':
                _require(stack and stack[-1][0] == ('[' if char == ']' else '{'))
                stack.pop()
            elif char == ':':
                _require(stack and stack[-1][0] == '{')
                stack[-1][1] += 1; _require(stack[-1][1] <= 64)
            elif char.isdigit() or char in '-+.':
                start = pos
                while pos < len(source) and source[pos] in '0123456789eE+-.':
                    pos += 1
                _require(re.fullmatch(r'0|[1-9][0-9]{0,9}', source[start:pos]) is not None)
                continue
            pos += 1
        _require(not stack)
        def pairs(items):
            result = {}
            for key, val in items:
                _require(key not in result); result[key] = val
            return result
        def invalid(_):
            raise ProbeUnavailable()
        return json.loads(source, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeUnavailable() from None


def _inventory(expected):
    _require(type(expected) is tuple and 1 <= len(expected) <= 256)
    _require(all(type(v) is str and v.isascii() and len(v) <= 128 and VERSION.fullmatch(v) for v in expected))
    _require(len(set(expected)) == len(expected))
    return sorted(expected)


def observe_catalog_ledger(transport, expected_versions: tuple[str, ...]) -> dict:
    expected = _inventory(expected_versions)  # no transaction on invalid input
    deadline = time.monotonic() + DEADLINE_SECONDS
    outbound = 0
    total_read = 0
    def check_deadline():
        if time.monotonic() >= deadline:
            raise ProbeTimedOut()
    def send(data):
        nonlocal outbound
        check_deadline()
        _require(type(data) is bytes and len(data) <= MAX_WRITE)
        outbound += len(data); _require(outbound <= MAX_OUTBOUND)
        # A transport must either finish the entire write within its bound or
        # raise. A numeric short-write result is never silently accepted.
        _require(transport.send(data) is None)
    def read():
        nonlocal total_read
        check_deadline()
        data = transport.read_frame(MAX_FRAME, deadline)
        check_deadline()
        _require(type(data) is bytes)
        total_read += len(data); _require(total_read <= 1048576)
        return _decode(data)
    try:
        send(BEGIN_SQL)
        send(CATALOG_SQL)
        validate_catalog(read())
        send(LEDGER_SQL)
        rows = read()
        _exact(rows, {'protocol_version': 3, 'phase': 'ledger_locked', 'count': len(expected),
                      'overflow': False, 'invalid': False, 'migrations': expected})
        send(FINISH_SQL)
        transport.close()
        check_deadline()
    except BaseException as exc:
        try:
            transport.send(ROLLBACK_SQL)
        except BaseException:
            pass
        try:
            transport.abort()
        except BaseException:
            pass
        if isinstance(exc, (ProbeTimedOut, TimeoutError)):
            raise ProbeTimedOut() from None
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise ProbeUnavailable() from None
    return {'protocol_version': 3, 'scope': 'disposable_schema_ledger', 'ledger_matches': True,
            'schema_attested': False, 'production_ready': False, 'deployment_authorized': False}
