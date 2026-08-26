"""Manifest-gated access to vendored upstream data."""

import functools
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "SOURCES.json"


class SourceError(RuntimeError):
    """Raised when vendored data is missing or does not match the manifest."""


def parse_manifest(text):
    """Parse manifest JSON, wrapping a decode failure as SourceError."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise SourceError(
            f"{MANIFEST} is not valid JSON ({error}); it is machine-generated, "
            "so re-run tools/vendor.py rather than editing it"
        ) from error


@functools.lru_cache(maxsize=1)
def load():
    if not MANIFEST.exists():
        raise SourceError(f"missing manifest {MANIFEST}; run tools/vendor.py")
    return parse_manifest(MANIFEST.read_text(encoding="utf-8"))


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


def rows_for(rel):
    """Load a vendored JSON file and return its data rows.

    Vendored files come in two shapes: a bare list, or an object with `_meta`
    and `data` keys. Both normalise to a list of rows.
    """
    payload = json.loads(path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


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


def verify_all():
    """Every file whose hash does not match, as a list of messages.

    Returns an empty list when everything matches. Unlike verify(), which stops
    at the first problem, this reports all of them — a data refresh can break
    several files at once and seeing one at a time wastes a cycle each.
    """
    problems = []
    for source in load()["sources"]:
        for rel, entry in source["files"].items():
            path = ROOT / entry["local"]
            if not path.exists():
                problems.append(f"{rel}: missing at {path}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                problems.append(
                    f"{rel}: hash mismatch, manifest {entry['sha256'][:12]}, "
                    f"on disk {digest[:12]}"
                )
    return problems
