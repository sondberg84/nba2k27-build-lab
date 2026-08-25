"""Badge definitions, height eligibility and tier requirements."""

import functools
import json

from buildlab import sources

# reference/enums.json defines discipline_order 0-5. The `tokens` and `slots`
# arrays in badges/token_contributions.json are indexed by this order.
DISCIPLINE_ORDER = (
    "finishing",
    "shooting",
    "playmaking",
    "defense",
    "rebounding",
    "physicals",
)

# definitions.json uses [63, 91] to mean "no height restriction". Legal build
# heights are 69-88, so that range can never exclude anything.
UNRESTRICTED = [63, 91]


def _rows(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


@functools.lru_cache(maxsize=1)
def definitions():
    return _rows("badges/definitions.json")


@functools.lru_cache(maxsize=1)
def _by_id():
    return {b["badge"]: b for b in definitions()}


@functools.lru_cache(maxsize=1)
def _by_name():
    return {b["name"]: b for b in definitions()}


def by_id(badge_id):
    index = _by_id()
    if badge_id not in index:
        raise KeyError(f"no badge with id {badge_id}")
    return index[badge_id]


def by_name(name):
    index = _by_name()
    if name not in index:
        raise KeyError(f"no badge named {name!r}")
    return index[name]


def height_eligible(badge_id, height_inches):
    low, high = by_id(badge_id)["height_inches"]
    return low <= height_inches <= high


def eligible_at_height(height_inches):
    """Badge ids usable at this height, ignoring attributes."""
    return tuple(
        b["badge"]
        for b in definitions()
        if b["allowed"] and height_eligible(b["badge"], height_inches)
    )
