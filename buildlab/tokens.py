"""Badge token costs, per-attribute contributions, and build-level estimates."""

import functools
import json

from buildlab import badges, sources

# Every legend row in token_costs.json has cost 0, and legend appears nowhere
# in tier_requirements.json. That is not "free" — legend is unreachable at
# build creation and only comes from a Max Plus 2 fuse slot.
UNREACHABLE_TIERS = ("legend",)


def _rows(rel):
    payload = json.loads(sources.path_for(rel).read_text(encoding="utf-8"))
    return payload["data"] if isinstance(payload, dict) else payload


def is_unreachable_tier(tier):
    return tier in UNREACHABLE_TIERS


@functools.lru_cache(maxsize=1)
def costs():
    return _rows("badges/token_costs.json")


@functools.lru_cache(maxsize=1)
def _cost_index():
    return {(r["badge"], r["tier"], r["height_inches"]): r["cost"] for r in costs()}


def cost_for(badge_id, tier, height_inches):
    index = _cost_index()
    key = (badge_id, tier, height_inches)
    if key not in index:
        raise KeyError(
            f"no token cost for badge {badge_id} tier {tier!r} at height "
            f"{height_inches}; costs cover heights 69-88"
        )
    return index[key]


def cost_of_loadout(loadout, height_inches, cumulative=False):
    """Total tokens to equip a {badge_id: tier} loadout at this height.

    The shipped data cannot settle whether a tier's cost is absolute or
    incremental, so this is a caller's choice:

    - cumulative=False (default): each badge costs exactly its own tier's
      shipped number. This matches token_costs.json's field description,
      where `tier` is "tier being equipped" and `cost` is "tokens required".
    - cumulative=True: a badge at gold costs bronze + silver + gold, on the
      reading that each row prices one tier STEP. This explains why the
      shipped numbers decrease with tier (3, 2, 1, 1), which is otherwise
      hard to account for.

    Neither reading is verified. If a future probe records a real token
    balance for a known loadout, that settles it.
    """
    total = 0
    for badge_id, tier in loadout.items():
        if is_unreachable_tier(tier):
            raise ValueError(
                f"badge {badge_id} at tier {tier!r} cannot be equipped at build "
                "creation; legend comes only from a Max Plus 2 fuse slot"
            )
        if not badges.height_eligible(badge_id, height_inches):
            low, high = badges.by_id(badge_id)["height_inches"]
            raise ValueError(
                f"badge {badge_id} is not eligible at height {height_inches}; "
                f"its range is {low}-{high}. The cost table carries rows for "
                "every height regardless of eligibility, so a raw cost_for "
                "lookup will happily price a badge you cannot equip."
            )
        if cumulative:
            steps = badges.TIERS[: badges.TIERS.index(tier) + 1]
            total += sum(cost_for(badge_id, step, height_inches) for step in steps)
        else:
            total += cost_for(badge_id, tier, height_inches)
    return total


@functools.lru_cache(maxsize=1)
def contributions():
    return _rows("badges/token_contributions.json")


@functools.lru_cache(maxsize=1)
def _contribution_index():
    return {
        (r["height_inches"], r["attribute"], r["rating"]): tuple(r["tokens"])
        for r in contributions()
    }


def contribution(height_inches, attribute, rating):
    """Tokens earned per discipline from ONE attribute at this rating.

    Measured with every other attribute at the 25 floor. Six values in
    badges.DISCIPLINE_ORDER. This is a measured fact; see estimate_earned for
    the build-level extrapolation and its caveat.
    """
    index = _contribution_index()
    key = (height_inches, attribute, rating)
    if key not in index:
        raise KeyError(
            f"no token contribution for height {height_inches}, attribute "
            f"{attribute}, rating {rating}; heights 69-88, attributes 0-20, "
            "ratings 25-99"
        )
    return index[key]
