"""Manifest-gated access to vendored upstream data."""

import functools
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "SOURCES.json"


class SourceError(RuntimeError):
    """Raised when vendored data is missing or does not match the manifest."""


@functools.lru_cache(maxsize=1)
def load():
    if not MANIFEST.exists():
        raise SourceError(f"missing manifest {MANIFEST}; run tools/vendor.py")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _entry(rel):
    for source in load()["sources"]:
        if rel in source["files"]:
            return source["files"][rel]
    raise SourceError(f"{rel} is not in the manifest")


def path_for(rel):
    path = ROOT / _entry(rel)["local"]
    if not path.exists():
        raise SourceError(f"missing vendored file {path}; run tools/vendor.py")
    return path


def verify():
    """Raise SourceError if any vendored file differs from its recorded hash."""
    for source in load()["sources"]:
        for rel, entry in source["files"].items():
            path = ROOT / entry["local"]
            if not path.exists():
                raise SourceError(f"missing vendored file {path}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                raise SourceError(
                    f"{rel} hash mismatch: manifest {entry['sha256'][:12]}, "
                    f"on disk {digest[:12]}"
                )
