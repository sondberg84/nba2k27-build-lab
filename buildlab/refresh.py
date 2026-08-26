"""Take new upstream data safely: check, stage, diff, judge, adopt.

Nothing here mutates live data until adopt() is called explicitly. The dataset
ships its own answer key, so a staged copy can be judged before it is trusted:
if the staged tables cannot reproduce the staged vectors, the capture is broken
and the refresh is refused.
"""

import hashlib
import json
import pathlib
import urllib.request

from buildlab import ovr, sources

STAGING = sources.ROOT / "data" / "staging"
SNAPSHOTS = sources.ROOT / "data" / "snapshots"

# The reference body every mixed vector was probed at: PG, 6'3", 198 lb, 78 in.
VECTOR_HEIGHT = 75

VERDICTS = ("real_change", "cosmetic", "upstream_broken")


def snapshot_dir(commit):
    return SNAPSHOTS / commit


def upstream_head(repo):
    """The current head SHA of a GitHub repository's default branch."""
    url = f"https://api.github.com/repos/{repo}/commits"
    with urllib.request.urlopen(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload[0]["sha"]


def pinned_commit():
    return sources.load()["sources"][0]["commit"]


def pinned_repo():
    url = sources.load()["sources"][0]["url"]
    return url.removeprefix("https://github.com/")


def check():
    """Compare the pin against upstream without downloading anything."""
    pinned = pinned_commit()
    head = upstream_head(pinned_repo())
    return {
        "pinned": pinned,
        "upstream": head,
        "behind": head != pinned,
    }


def stage(commit):
    """Download every manifested upstream file at a commit into staging."""
    STAGING.mkdir(parents=True, exist_ok=True)
    source = sources.load()["sources"][0]
    repo = pinned_repo()
    staged = {}
    for rel, entry in source["files"].items():
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{rel}"
        with urllib.request.urlopen(url) as response:
            payload = response.read()
        out = STAGING / pathlib.Path(entry["local"]).name
        out.write_bytes(payload)
        staged[rel] = {
            "path": out,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "changed": hashlib.sha256(payload).hexdigest() != entry["sha256"],
        }
    return staged


def staged_rows(staged, rel):
    payload = json.loads(staged[rel]["path"].read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


def diff_rows(before, after, key):
    """Semantic diff of two row lists, keyed by a tuple of field names.

    Returns a list of `{"key", "kind", "fields"}`. `kind` is added, removed or
    changed; `fields` maps each differing field to a (before, after) pair.
    Order-independent.
    """

    def index(rows):
        return {tuple(row[k] for k in key): row for row in rows}

    old, new = index(before), index(after)
    changes = []
    for identity in sorted(set(old) | set(new), key=repr):
        if identity not in new:
            changes.append({"key": identity, "kind": "removed", "fields": {}})
            continue
        if identity not in old:
            changes.append({"key": identity, "kind": "added", "fields": {}})
            continue
        fields = {
            field: (old[identity][field], new[identity][field])
            for field in new[identity]
            if old[identity].get(field) != new[identity][field]
        }
        if fields:
            changes.append({"key": identity, "kind": "changed", "fields": fields})
    return changes


def check_vectors(rows):
    """Whether the live engine reproduces a set of golden vectors.

    Used against STAGED vectors to decide whether a refresh is a real rules
    change or a broken capture.
    """
    matched = 0
    failures = []
    for row in rows:
        got = ovr.overall(VECTOR_HEIGHT, row["values"])
        if got == row["overall"]:
            matched += 1
        else:
            failures.append(
                {"sample": row.get("sample"), "expected": row["overall"], "got": got}
            )
    return {
        "reproduces": not failures,
        "matched": matched,
        "total": len(rows),
        "failures": failures[:5],
    }
