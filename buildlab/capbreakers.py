"""Cap breaker gains: how much each of the five applications raises an attribute."""

import functools
import json

from buildlab import sources

SCENARIOS = ("isolated", "near_caps")
APPLICATIONS = 5
MAX_RATING = 99

# The table was probed at exactly this body. Coverage for each attribute stops
# at that attribute's ceiling here — verified against body.ceilings for all 21
# attributes with zero mismatches. Results for any other body are therefore
# unverified, and a sequence can be asked to start above coverage.
REFERENCE_BODY = {"height": 75, "weight": 198, "wingspan": 78}

OUT_OF_RANGE_NOTE = (
    "ran past the highest rating this table covers for the attribute; the data "
    "was probed at the reference body (PG, 6'3, 198 lb, 78 in wingspan) and "
    "stops at that body's ceiling"
)


def _rows(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


@functools.lru_cache(maxsize=1)
def gains():
    return _rows("cap_breakers/gains_by_rating.json")


@functools.lru_cache(maxsize=1)
def _gain_index():
    return {
        (r["scenario"], r["attribute"], r["rating"], r["application"]): r["gain"]
        for r in gains()
    }


def gain_for(scenario, attribute, rating, application):
    index = _gain_index()
    key = (scenario, attribute, rating, application)
    if key not in index:
        raise KeyError(
            f"no cap breaker gain for scenario {scenario!r}, attribute "
            f"{attribute}, rating {rating}, application {application}; "
            f"scenarios are {SCENARIOS}, applications 0-{APPLICATIONS - 1}"
        )
    return index[key]


@functools.lru_cache(maxsize=None)
def max_rating_for(scenario, attribute):
    """Highest rating this table covers for an attribute under a scenario."""
    ratings = [
        key[2] for key in _gain_index() if key[0] == scenario and key[1] == attribute
    ]
    if not ratings:
        raise KeyError(f"no cap breaker data for {scenario!r}, attribute {attribute}")
    return max(ratings)


def apply_all(scenario, attribute, rating):
    """Apply the five cap breakers in sequence, reporting how far it got.

    Each application looks up its gain at the rating the previous one produced,
    not at the original rating.

    Returns a dict with `rating` (the result), `applied` (how many of the five
    actually landed), `complete` (whether all five did) and `note` (empty
    unless the sequence ran out of data). A sequence that walks past the
    reference body's ceiling for this attribute stops early — that is reported,
    never silently truncated.
    """
    current = rating
    applied = 0
    note = ""
    for application in range(APPLICATIONS):
        try:
            current += gain_for(scenario, attribute, current, application)
        except KeyError:
            note = OUT_OF_RANGE_NOTE
            break
        current = min(current, MAX_RATING)
        applied += 1
    return {
        "rating": current,
        "applied": applied,
        "complete": applied == APPLICATIONS,
        "note": note,
    }
