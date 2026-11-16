"""Validate an offloaded review receipt; never dispatch a runtime operation."""
import argparse
import json
import os
from pathlib import Path
import stat

MIB = 1024 ** 2
HOME_RESERVE = 5 * 1024 ** 3
HOME_DRIFT = 128 * MIB
DOCKER_RESERVE = 813694976
DOCKER_DRIFT = 64 * MIB
CAPS = {"archive": 36 * MIB, "source": 40 * MIB,
        "backup_toc": 24 * MIB, "helpers_seals": 8 * MIB,
        "scratch": 20 * MIB}
PINS = {
    "gate_sha": "33bf1c9c3ee606e140258397622f8732c5669438",
    "helper_sha": "4246264a881382676927e22adad0a1d240f03268",
    "product_sha": "a82b31dc8850aa3956972928b8c720969765a972",
    "product_tree": "11503a735d7d983ca3ebf090b471c89682e77278",
    "image": "sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7",
    "serving": "17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e",
    "secondary": "343896791b0377600b9825b53c1ddb1b179d54c424d19ea935c0b9b8a681eb07",
    "public_pid": 1293423,
    "public_start_ticks": "19892443",
    "public_binary_sha256": "bb11d963666e4fc44f6b0879ebb55a14cf7b2ca221bad6ffa8d3282d5360203e",
}


def load_receipt(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size > 65536):
            raise ValueError("receipt_metadata")
        return json.loads(stream.read(65537))


def plan(receipt):
    if receipt.get("pins") != PINS:
        raise ValueError("pin_drift")
    if receipt.get("public_slot_released") is not False:
        raise ValueError("new_release_requires_fresh_gate")
    if receipt.get("execution_authorized") is not False:
        raise ValueError("execution_forbidden")
    for name in ("public_package_accounted", "public_install_accounted"):
        if type(receipt.get(name)) is not bool:
            raise ValueError("allocation_accounting")
    capacity = receipt.get("capacity", {})
    for name in ("home_free", "docker_free", "offloaded_free"):
        if type(capacity.get(name)) is not int or capacity[name] < 0:
            raise ValueError("capacity_metadata")
    future_public = ((not receipt["public_package_accounted"]) * 128 * MIB
                     + (not receipt["public_install_accounted"]) * 64 * MIB)
    home = HOME_RESERVE + HOME_DRIFT + sum(CAPS.values()) + future_public
    docker = DOCKER_RESERVE + DOCKER_DRIFT + 64 * MIB
    fits = (capacity["home_free"] >= home and capacity["docker_free"] >= docker
            and capacity["offloaded_free"] >= 64 * MIB)
    phases = [
        {"phase": "release_and_sync", "requires": [
            "independent public readback", "explicit coordinator slot release",
            "fresh Issue401/Project8/docs/record/preflight", "fresh identity and capacity proof"]},
        {"phase": "immutable_product", "requires": [
            "exact a82 git archive and full inventory", "physical source/archive fsync",
            "no builds or pulls", "recheck caps before each allocation"]},
        {"phase": "actual_image_fixture", "requires": [
            "reviewed adapter and owned synthetic network/UUID DB/bucket",
            "actual cached3132 HTTP/child/PG/read_only/SVG proof",
            "no provider/payment/model calls or persistent shared-role changes",
            "owned cleanup and serving/public identities unchanged"]},
        {"phase": "backup_baseline", "requires": [
            "root-reviewed bounded SQL/backup commands before SQL",
            "physical dump/TOC and compact coherent protected27/catalog12 snapshot",
            "no automatic DB restore"]},
        {"phase": "activation_review", "requires": [
            "fresh external activator/launcher source gate and offline seal tests",
            "exact candidate create/config lifecycle hashes and independent review",
            "verified retained17295 rollback; candidate termination proof before old start",
            "health/commerce only; no catalog request"]},
        {"phase": "initial_probe_separate", "requires": [
            "new reviewed initial-job and internal Go POST end/fence proof",
            "configuration START/FIN helper is insufficient",
            "no historical configuration probe replay"]},
    ]
    return {
        "status": "VALID_DRY_PLAN_EXECUTION_HELD" if fits else "VALID_DRY_PLAN_CAPACITY_BLOCKED",
        "execution_authorized": False, "public_slot_released": False,
        "measurements_are_reservations": False, "pins": PINS,
        "private_home_caps": CAPS, "private_home_cap": sum(CAPS.values()),
        "home_admission": home, "home_end_floor": HOME_RESERVE + HOME_DRIFT,
        "future_public_allocation": future_public, "docker_admission": docker,
        "docker_end_floor": DOCKER_RESERVE + DOCKER_DRIFT,
        "offloaded_fixture_cap": 64 * MIB,
        "capacity_snapshot_fits": fits, "capacity_snapshot": capacity,
        "phase_order": phases,
        "unresolved": ["public slot release", "actual-image fixture adapter and run",
                       "physical package/backup", "reviewed activation adapter",
                       "separate initial-selector end/fence proof"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = plan(load_receipt(args.receipt))
    except (ValueError, OSError, TypeError):
        print(json.dumps({"status": "REFUSED", "execution_authorized": False}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
