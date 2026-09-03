"""Fast-lane ingestion worker package boundary."""


def run_once():
    """Lazily expose the worker entrypoint without preloading ``worker``."""

    from .worker import run_once as _run_once

    return _run_once()

__all__ = ["run_once"]
