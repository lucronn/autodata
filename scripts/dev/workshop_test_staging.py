#!/usr/bin/env python3
"""Offline TEST renderer and guarded launchers; render never activates runtime."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import time
import unicodedata
from urllib.parse import urlsplit

PROJECT = "autodata-workshop-stripe-staging-20261116"
RUNTIME_ROOT = Path("/home/corp/autodata-evidence") / PROJECT
DATABASE = "workshop_stripe_staging"
BUCKET = "workshop-stripe-staging-sources"
STAGING_ENVIRONMENT = {
    "AUTODATA_ENV": "staging",
    "AUTODATA_DB_ADDRESS": "postgres:5432",
    "AUTODATA_POSTGRES_DB": DATABASE,
    "AUTODATA_POSTGRES_USER": DATABASE,
    "AUTODATA_S3_ADDRESS": "minio:9000",
    "AUTODATA_S3_ENDPOINT": "minio:9000",
    "AUTODATA_SOURCE_BUCKET": BUCKET,
    "AUTODATA_NATS_ADDRESS": "nats:4222",
    "AUTODATA_SOURCE_PERSIST": "0",
}
COMMON = {"AUTODATA_POSTGRES_PASSWORD", "AUTODATA_S3_ACCESS_KEY",
          "AUTODATA_S3_SECRET_KEY", "AUTODATA_INGESTION_INTERNAL_TOKEN"}
ROLE_KEYS = {
    "api": COMMON | {"AUTODATA_IMAGE_URL_KEY"},
    "ingestion": COMMON | {"AUTODATA_STRIPE_SECRET_KEY", "AUTODATA_STRIPE_WEBHOOK_SECRET"},
    "reconciler": COMMON | {"AUTODATA_STRIPE_SECRET_KEY", "AUTODATA_STRIPE_WEBHOOK_SECRET"},
}
LAUNCHER = "/src/scripts/dev/workshop_test_staging.py"
COMMANDS = {"api": ["/runtime/autodata-api"],
            "ingestion": [sys.executable, "-m", "autodata_ingestion.http_service"],
            "reconciler": [sys.executable, "-I", LAUNCHER, "bounded-reconcile"]}
API_ENVIRONMENT = {
    "AUTODATA_AUTH_MODE": "firebase",
    "AUTODATA_API_ADDR": ":8080",
    "AUTODATA_PROJECTION_STORE": "postgres",
    "AUTODATA_INGESTION_URL": "http://ingestion-http:8081",
    "GOOGLE_APPLICATION_CREDENTIALS": "/run/staging/firebase-adc.json",
}
INHERITED_CLEAR = {"AUTODATA_BANKONE_API_KEY", "AUTODATA_BANKTWO_API_KEY",
                   "BANKONE_BASE_URL", "BANKTWO_BASE_URL",
                   "AUTODATA_MINIO_ROOT_USER", "AUTODATA_MINIO_ROOT_PASSWORD",
                   "INCEPTION_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                   "GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
                   "GOOGLE_CLOUD_QUOTA_PROJECT", "FIREBASE_CONFIG", "FIREBASE_AUTH_EMULATOR_HOST",
                   "AUTODATA_FIREBASE_PROJECT_ID", "AUTODATA_FIREBASE_WEB_API_KEY",
                   "AUTODATA_FIREBASE_WEB_APP_ID", "AUTODATA_FIREBASE_AUTH_DOMAIN",
                   "AUTODATA_STRIPE_ACCOUNT_ID", "AUTODATA_STRIPE_PRICE_ID",
                   "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"}
PUBLIC_COMMON = {"PATH", "LANG", "LC_ALL", "PYTHONPATH", "AUTODATA_DB_ADDRESS",
                 "AUTODATA_POSTGRES_DB", "AUTODATA_POSTGRES_USER", "AUTODATA_S3_ADDRESS",
                 "AUTODATA_S3_ENDPOINT", "AUTODATA_SOURCE_BUCKET", "AUTODATA_NATS_ADDRESS",
                 "AUTODATA_ENV", "AUTODATA_PUBLIC_ORIGIN", "AUTODATA_COMMERCE_MODE",
                 "AUTODATA_SOURCE_REGION", "AUTODATA_SOURCE_PERSIST", "BASE44_PREVIEW_MODE",
                 "AUTODATA_STRIPE_ACCOUNT_ID", "AUTODATA_STRIPE_PRICE_ID"}
PUBLIC_KEYS = {
    "api": PUBLIC_COMMON | {"AUTODATA_AUTH_MODE", "AUTODATA_API_ADDR", "AUTODATA_PROJECTION_STORE",
        "AUTODATA_INGESTION_URL", "AUTODATA_WORKSHOP_TESTER_UIDS_JSON", "GOOGLE_APPLICATION_CREDENTIALS",
        "AUTODATA_FIREBASE_PROJECT_ID", "AUTODATA_FIREBASE_WEB_API_KEY", "AUTODATA_FIREBASE_WEB_APP_ID",
        "AUTODATA_FIREBASE_AUTH_DOMAIN"},
    "ingestion": PUBLIC_COMMON | {"AUTODATA_INGESTION_HTTP_ADDR", "AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON"},
    "reconciler": PUBLIC_COMMON | {"AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON"},
}


def fail():
    raise ValueError("invalid isolated TEST staging input")


def unique_object(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            fail()
        d[k] = v
    return d


def origin_valid(origin):
    if not isinstance(origin, str):
        return False
    host = urlsplit(origin).hostname
    if (not host or len(host) > 253 or origin != "https://" + host or
            host in {"cars.tk", "autodata.cars.tk", "autodata.curtis.click"}):
        return False
    # The generated purchase notice URLs use this host verbatim.
    labels = host.split(".")
    return (len(labels) >= 2 and bool(re.fullmatch(r"[a-z]{2,63}", labels[-1])) and
            all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels))


def private_material(path, role, enabled):
    path = Path(path)
    if role not in ROLE_KEYS or path.absolute() != path.resolve():
        fail()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600 or st.st_uid != os.getuid() or st.st_size > 65536:
            fail()
        try:
            d = json.loads(f.read(), object_pairs_hook=unique_object)
        except (ValueError, UnicodeError):
            fail()
    if not isinstance(d, dict) or set(d) - ROLE_KEYS[role]:
        fail()
    if role == "reconciler" and not enabled:
        fail()
    if not enabled and set(d) & {"AUTODATA_STRIPE_SECRET_KEY", "AUTODATA_STRIPE_WEBHOOK_SECRET"}:
        fail()
    required = COMMON | ({"AUTODATA_IMAGE_URL_KEY"} if role == "api" else set())
    if enabled and role in {"ingestion", "reconciler"}:
        required |= {"AUTODATA_STRIPE_SECRET_KEY", "AUTODATA_STRIPE_WEBHOOK_SECRET"}
    if not required <= set(d) or any(not isinstance(v, str) or not v or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in v) for v in d.values()):
        fail()
    if any("sk_live_" in v or "rk_live_" in v for v in d.values()):
        fail()
    if "AUTODATA_STRIPE_SECRET_KEY" in d and not d["AUTODATA_STRIPE_SECRET_KEY"].startswith("sk_test_"):
        fail()
    return d


def stripe_ids_valid(account, price):
    return (isinstance(account, str) and re.fullmatch(r"acct_[A-Za-z0-9]+", account) and
            isinstance(price, str) and re.fullmatch(r"price_[A-Za-z0-9]+", price))


def tester_uid_json(ids):
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 100 or
            any(not isinstance(uid, str) or not 1 <= len(uid) <= 128 or not uid.strip() or
                any(unicodedata.category(char) in {"Cc", "Cs"} for char in uid) for uid in ids) or
            len(set(ids)) != len(ids)):
        fail()
    raw = json.dumps(ids, ensure_ascii=False, separators=(",", ":"))
    if len(raw.encode("utf-8")) > 32768:
        fail()
    return raw


def public_profile(p):
    if not isinstance(p, dict) or set(p) != {"origin", "tester_uids", "firebase", "stripe", "source_sha", "binary_sha256", "runtime_image_id", "enabled"}:
        fail()
    if not origin_valid(p["origin"]):
        fail()
    f = p["firebase"]
    if (not isinstance(f, dict) or set(f) != {"project_id", "api_key", "app_id", "auth_domain"} or
            not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", f["project_id"]) or
            not re.fullmatch(r"1:[0-9]+:web:[a-zA-Z0-9]+", f["app_id"]) or
            f["auth_domain"] != f["project_id"] + ".firebaseapp.com" or
            not f["api_key"] or f["api_key"].strip() != f["api_key"]):
        fail()
    if (type(p["enabled"]) is not bool or not re.fullmatch(r"[0-9a-f]{40}", p["source_sha"]) or
            not re.fullmatch(r"[0-9a-f]{64}", p["binary_sha256"]) or
            not re.fullmatch(r"sha256:[0-9a-f]{64}", p["runtime_image_id"])):
        fail()
    stripe = p["stripe"]
    if stripe is not None or p["enabled"]:
        if (not isinstance(stripe, dict) or set(stripe) != {"account_id", "price_id"} or
                not stripe_ids_valid(stripe["account_id"], stripe["price_id"])):
            fail()
    tester_uids = tester_uid_json(p["tester_uids"])
    return p, tester_uids


def staging_commerce_mode(env):
    mode = env.get("AUTODATA_COMMERCE_MODE")
    if (mode not in {"disabled", "stripe_test"} or not origin_valid(env.get("AUTODATA_PUBLIC_ORIGIN")) or
            any(env.get(key) != value for key, value in STAGING_ENVIRONMENT.items())):
        fail()
    if mode == "stripe_test" and not stripe_ids_valid(env.get("AUTODATA_STRIPE_ACCOUNT_ID"), env.get("AUTODATA_STRIPE_PRICE_ID")):
        fail()
    return mode


def launch_command(role):
    return ["/usr/local/bin/python", "-I", LAUNCHER, "exec", "--role", role, "--private", "/run/staging/private.json"]


def render(p, root=RUNTIME_ROOT):
    p, tester_uids = public_profile(p)
    root = Path(root)
    if root != RUNTIME_ROOT or root.absolute() != root.resolve():
        fail()
    repo = Path(__file__).resolve().parents[2]
    c = json.loads((repo / "infra/compose/compose.workshop-local-empty.yaml").read_text())
    c["name"] = PROJECT
    c["networks"] = {"internal": {"internal": True, "name": PROJECT + "_internal"},
                     "egress": {"name": PROJECT + "_egress"}}
    services = c["services"]
    python_image = p["runtime_image_id"]
    if python_image == services["ingestion-http"]["image"]:
        fail()
    secret = str(root / "private")
    for s in services.values():
        s["environment"] = {}
        for m in s["volumes"]:
            m["source"] = m["source"].replace("${M1_ROOT:?required}", str(root))
        s.pop("ports", None)
        s["restart"] = "no"
    def bind(source, target):
        return {"type": "bind", "source": source, "target": target, "read_only": True,
                "bind": {"create_host_path": False}}
    db = DATABASE
    services["postgres"]["environment"] = {"POSTGRES_DB": db, "POSTGRES_USER": db, "POSTGRES_PASSWORD_FILE": "/run/staging/pg-password"}
    services["postgres"]["volumes"].append(bind(secret + "/pg-password", "/run/staging/pg-password"))
    services["postgres"]["healthcheck"]["test"] = ["CMD", "pg_isready", "-h", "127.0.0.1", "-U", db, "-d", db]
    services["minio"]["environment"] = {"S3_BUCKET": BUCKET}
    services["minio"]["entrypoint"] = ["/bin/sh", "-ec"]
    services["minio"]["command"] = ['AWS_ACCESS_KEY_ID="$$(cat /run/staging/s3-access)"; AWS_SECRET_ACCESS_KEY="$$(cat /run/staging/s3-secret)"; export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; exec /entrypoint.sh mini -dir=/data -s3.port=9000']
    services["minio"]["volumes"] += [bind(secret + "/s3-access", "/run/staging/s3-access"), bind(secret + "/s3-secret", "/run/staging/s3-secret")]
    services["migration-runner"]["environment"] = {"PGHOST": "postgres", "PGPORT": "5432", "PGUSER": db, "PGDATABASE": db, "PGPASSFILE": "/run/staging/pgpass"}
    services["migration-runner"]["volumes"].append(bind(secret + "/pgpass", "/run/staging/pgpass"))
    services["migration-runner"]["depends_on"] = {"postgres": {"condition": "service_healthy"}}
    common = {**STAGING_ENVIRONMENT, "AUTODATA_PUBLIC_ORIGIN": p["origin"],
              "AUTODATA_COMMERCE_MODE": "stripe_test" if p["enabled"] else "disabled"}
    # Keep provider configuration role-specific even before the launcher runs.
    common.update({k: "" for k in INHERITED_CLEAR | set().union(*ROLE_KEYS.values())})
    common.update({"AUTODATA_SOURCE_REGION": "US", "BASE44_PREVIEW_MODE": "0"})
    if p["enabled"]:
        common.update({"AUTODATA_STRIPE_ACCOUNT_ID": p["stripe"]["account_id"], "AUTODATA_STRIPE_PRICE_ID": p["stripe"]["price_id"]})
    for name, role in [("api", "api"), ("ingestion-http", "ingestion")]:
        s = services[name]
        s["image"] = python_image
        s["environment"] = copy.deepcopy(common)
        s["networks"] = ["internal", "egress"]
        s["working_dir"] = "/src"
        s["volumes"] = [bind(str(root / "source"), "/src"), bind(secret + "/" + role + ".json", "/run/staging/private.json")]
        s["entrypoint"] = []
        s["command"] = launch_command(role)
        s["depends_on"] = {"migration-runner": {"condition": "service_completed_successfully"},
                           "minio": {"condition": "service_healthy"}, "nats": {"condition": "service_healthy"}}
    api = services["api"]
    api["volumes"] += [bind(str(root / "bin/autodata-api"), "/runtime/autodata-api"), bind(secret + "/firebase-adc.json", "/run/staging/firebase-adc.json")]
    api["ports"] = [{"target": 8080, "published": "3043", "host_ip": "127.0.0.1", "protocol": "tcp"}]
    api["depends_on"]["ingestion-http"] = {"condition": "service_healthy"}
    api["environment"].update({**API_ENVIRONMENT,
        "AUTODATA_WORKSHOP_TESTER_UIDS_JSON": tester_uids,
        **{"AUTODATA_FIREBASE_" + k.upper(): v for k, v in {"project_id":p["firebase"]["project_id"], "web_api_key":p["firebase"]["api_key"], "web_app_id":p["firebase"]["app_id"], "auth_domain":p["firebase"]["auth_domain"]}.items()}})
    notices = {"enabled": p["enabled"], "terms_version": "workshop-v1", **{k + "_url": p["origin"] + "/workshop/test-notices/" + name if p["enabled"] else None for k, name in [("terms", "terms"), ("privacy", "privacy"), ("refund", "refund"), ("contact", "contact")]}, "tax_notice": "Stripe TEST only: the displayed USD20 is simulated; no actual payment or tax is collected." if p["enabled"] else None}
    services["ingestion-http"]["environment"].update({"PYTHONPATH": "/src/workers/ingestion-python/src:/src/packages/contracts/python:/src/workers/enrichment-python/src", "AUTODATA_INGESTION_HTTP_ADDR": ":8081", "AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON": json.dumps(notices, separators=(",", ":"))})
    if p["enabled"]:
        reconciler = copy.deepcopy(services["ingestion-http"])
        reconciler["command"] = launch_command("reconciler")
        reconciler["volumes"] = [bind(str(root / "source"), "/src"), bind(secret + "/reconciler.json", "/run/staging/private.json")]
        reconciler["environment"].pop("AUTODATA_INGESTION_HTTP_ADDR", None)
        reconciler.pop("healthcheck", None)
        reconciler["depends_on"] = {"ingestion-http": {"condition": "service_healthy"}}
        reconciler.update({"mem_limit": "384m", "cpus": 0.5, "init": True, "stop_grace_period": "10s"})
        services["payment-reconciler"] = reconciler
    for service in services.values():
        for mount in service["volumes"]:
            source = Path(mount["source"])
            if not source.is_relative_to(root) or source.resolve() != source:
                fail()
        service["environment"] = {key: value.replace("$", "$$") for key, value in service["environment"].items()}
    wire = json.dumps(c, indent=2)
    if "${" in wire or "M1_" in wire or "local-m1" in wire:
        fail()
    return c


def reconciler_environment(env):
    if staging_commerce_mode(env) != "stripe_test":
        fail()
    if any(not isinstance(env.get(k), str) or not env[k] or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in env[k]) for k in ROLE_KEYS["reconciler"]):
        fail()
    if not env["AUTODATA_STRIPE_SECRET_KEY"].startswith("sk_test_"):
        fail()
    child = {k:v for k,v in env.items() if k in PUBLIC_KEYS["reconciler"] | ROLE_KEYS["reconciler"]}
    if any("sk_live_" in v or "rk_live_" in v for v in child.values()):
        fail()
    return child


def bounded_reconcile(*, env=None, run=subprocess.run, monotonic=time.monotonic, sleep=time.sleep):
    """Bound the unchanged runner's real pending-payment and SQL scheduling pass."""
    child = reconciler_environment(os.environ if env is None else env)
    deadline = monotonic() + 600
    command = [sys.executable, str(Path(__file__).resolve().with_name("reconcile_payments.py")), "--once", "--batch-size", "10"]
    for index in range(10):
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        try:
            result = run(command, env=child, timeout=min(45, remaining), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except (subprocess.TimeoutExpired, OSError):
            print("TEST reconciliation stopped: child unavailable or timed out", flush=True)
            return 2
        if result.returncode != 0 or monotonic() > deadline:
            print("TEST reconciliation stopped: child failed or budget exceeded", flush=True)
            return 2
        print("TEST reconciliation pass complete", flush=True)
        if index < 9:
            remaining = deadline - monotonic()
            if remaining > 0:
                sleep(min(15, remaining))
    print("TEST reconciliation bounded run complete", flush=True)
    return 0


def verify_source(source, source_sha):
    """Compare actual runtime bytes with Git objects, not a claimed sidecar SHA."""
    repo = Path(__file__).resolve().parents[2]
    expected = set()
    proc = subprocess.Popen(["git", "-C", str(repo), "archive", "--format=tar", source_sha], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
            for member in archive:
                target = source / member.name
                if not target.is_relative_to(source) or target.absolute() != target.resolve():
                    fail()
                if member.isdir():
                    continue
                if not member.isfile() or not target.is_file():
                    fail()
                expected.add(member.name)
                if hashlib.sha256(archive.extractfile(member).read()).digest() != hashlib.sha256(target.read_bytes()).digest():
                    fail()
        if proc.wait() != 0 or expected != {str(x.relative_to(source)) for x in source.rglob("*") if x.is_file()}:
            fail()
    finally:
        proc.stdout.close()
        if proc.poll() is None:
            proc.terminate()
            proc.wait()


def main():
    a = argparse.ArgumentParser(description=__doc__)
    sub = a.add_subparsers(dest="action", required=True)
    r = sub.add_parser("render"); r.add_argument("--profile", type=Path, required=True)
    x = sub.add_parser("exec"); x.add_argument("--role", choices=ROLE_KEYS, required=True); x.add_argument("--private", type=Path, required=True)
    sub.add_parser("bounded-reconcile")
    args = a.parse_args()
    try:
        if args.action == "render":
            p = json.loads(args.profile.read_text(), object_pairs_hook=unique_object)
            c = render(p)
            manifest = json.loads((RUNTIME_ROOT / "source-identity.json").read_text())
            binary = RUNTIME_ROOT / "bin/autodata-api"
            if manifest != {"source_sha": p["source_sha"]} or hashlib.sha256(binary.read_bytes()).hexdigest() != p["binary_sha256"]:
                fail()
            verify_source(RUNTIME_ROOT / "source", p["source_sha"])
            print(json.dumps(c, indent=2))
        elif args.action == "bounded-reconcile":
            return bounded_reconcile()
        else:
            enabled = staging_commerce_mode(os.environ) == "stripe_test"
            if args.role == "api" and (not os.environ.get("AUTODATA_WORKSHOP_TESTER_UIDS_JSON") or
                    any(os.environ.get(key) != value for key, value in API_ENVIRONMENT.items())):
                fail()
            values = private_material(args.private, args.role, enabled)
            # Start from a role-specific public allowlist: unknown image or
            # ambient credentials never cross into the child environment.
            env = {k:v for k,v in os.environ.items() if k in PUBLIC_KEYS[args.role]}
            if not enabled:
                env.pop("AUTODATA_STRIPE_ACCOUNT_ID", None)
                env.pop("AUTODATA_STRIPE_PRICE_ID", None)
            env.update(values)
            if args.role == "reconciler":
                env = reconciler_environment(env)
            os.execvpe(COMMANDS[args.role][0], COMMANDS[args.role], env)
    except (ValueError, OSError, KeyError, TypeError, AttributeError, tarfile.TarError):
        print("isolated TEST staging refused invalid input", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
