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


# Ordered worst to best. `legend` is deliberately absent: it has no attribute
# requirement anywhere in tier_requirements.json and every legend row in
# token_costs.json has cost 0, because it is not purchasable at build creation.
TIERS = ("bronze", "silver", "gold", "hall_of_fame")


@functools.lru_cache(maxsize=1)
def tier_requirements():
    return _rows("badges/tier_requirements.json")


@functools.lru_cache(maxsize=1)
def _requirements_index():
    return {(r["badge"], r["tier"]): r["requirements"] for r in tier_requirements()}


def requirements_for(badge_id, tier):
    index = _requirements_index()
    if (badge_id, tier) not in index:
        raise KeyError(
            f"no requirements for badge {badge_id} at tier {tier!r}; "
            f"tiers with requirements are {TIERS}"
        )
    return index[(badge_id, tier)]


def meets(badge_id, tier, values):
    """Whether a 21-value attribute vector satisfies this badge tier.

    Requirement lists hold one or two entries. Two entries are joined by the
    `operator_to_next` of the FIRST entry. The operator on the last entry is a
    terminator with nothing to join to and is ignored.
    """
    requirements = requirements_for(badge_id, tier)
    if len(requirements) not in (1, 2):
        raise ValueError(
            f"badge {badge_id} tier {tier!r} has {len(requirements)} requirements; "
            "only 1 or 2 are understood, and the join logic below would silently "
            "ignore the rest"
        )
    satisfied = [values[r["attribute"]] >= r["minimum"] for r in requirements]
    if len(satisfied) == 1:
        return satisfied[0]
    if requirements[0]["operator_to_next"] == "OR":
        return satisfied[0] or satisfied[1]
    return satisfied[0] and satisfied[1]


def best_tier(badge_id, values, height_inches):
    """Highest tier this build qualifies for, or None.

    Every badge has all four tiers today, asserted by
    test_every_badge_has_all_four_tiers. A missing tier therefore means the
    data changed, and that must raise rather than be silently skipped.
    """
    if not height_eligible(badge_id, height_inches):
        return None
    best = None
    for tier in TIERS:
        if meets(badge_id, tier, values):
            best = tier
    return best


def unlocked(values, height_inches):
    """Badge id -> best qualifying tier, for every badge this build unlocks."""
    out = {}
    for badge_id in eligible_at_height(height_inches):
        tier = best_tier(badge_id, values, height_inches)
        if tier is not None:
            out[badge_id] = tier
    return out
