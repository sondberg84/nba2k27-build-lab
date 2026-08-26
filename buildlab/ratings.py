"""Hand-authored animation quality scores.

The animation requirements are known from data. The quality is not, and will
not be until the game ships and somebody plays it. This module holds that
judgement, keyed by family and name.

Deliberately NOT manifested: it is authored, not vendored, so hash-pinning it
would make every edit look like corruption. Nothing in tools/ writes it.
"""

import functools
import json

from buildlab import animations, sources

PATH = sources.ROOT / "data" / "ratings.json"

SCORE_FIELDS = ("speed", "block_resistance")
TIERS = ("S", "A", "B", "C", "D")
TIER_ORDER = {tier: index for index, tier in enumerate(TIERS)}
SEPARATOR = "::"


@functools.lru_cache(maxsize=1)
def _document():
    if not PATH.exists():
        raise sources.SourceError(
            f"missing {PATH}; it holds your own animation ratings and is not "
            "vendored, so create it with an empty ratings object"
        )
    # Deliberately not sources.parse_manifest: that error tells you to re-run
    # tools/vendor.py, which is exactly the wrong advice for a file you wrote
    # by hand.
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise sources.SourceError(
            f"{PATH} is not valid JSON ({error}); it is hand-edited, so fix the "
            "syntax rather than regenerating it — no tool writes this file"
        ) from error


def meta():
    return _document()["_meta"]


def all_ratings():
    return _document()["ratings"]


def key_for(name, family):
    """The lookup key for a package. Family first so keys sort by family."""
    return f"{family}{SEPARATOR}{name}"


def rating_for(name, family, table=None):
    """This package's rating, or None if it has not been judged yet.

    Raises if the package does not exist, so a typo in the ratings file is a
    loud error rather than a silently unrated animation.
    """
    animations.by_name(name, family)
    source = all_ratings() if table is None else table
    return source.get(key_for(name, family))


def validate(table):
    """Every problem with a ratings table, as a list of messages."""
    problems = []
    for key, entry in sorted(table.items()):
        family, separator, name = key.partition(SEPARATOR)
        if not separator:
            problems.append(f"{key!r}: expected 'Family{SEPARATOR}Name'")
            continue
        try:
            animations.by_name(name, family)
        except KeyError:
            problems.append(f"{key!r}: no such package")
            continue
        for field in SCORE_FIELDS:
            if field not in entry:
                continue
            value = entry[field]
            if not isinstance(value, int) or not 1 <= value <= 10:
                problems.append(f"{key!r}: {field} must be an integer 1-10, got {value!r}")
        if "tier" in entry and entry["tier"] not in TIERS:
            problems.append(
                f"{key!r}: tier must be one of {TIERS}, got {entry['tier']!r}"
            )
    return problems


def _score(entry):
    """Sort key: rated before unrated, better tier first, then mean score."""
    if entry is None:
        return (1, len(TIERS), 0)
    tier = TIER_ORDER.get(entry.get("tier"), len(TIERS))
    scores = [entry[f] for f in SCORE_FIELDS if f in entry]
    mean = sum(scores) / len(scores) if scores else 0
    return (0, tier, -mean)


def rank(rows, table=None):
    """Order packages best-first, leaving unrated ones in their original order."""
    source = all_ratings() if table is None else table
    return sorted(
        rows,
        key=lambda row: _score(source.get(key_for(row["name"], row["family"]))),
    )
