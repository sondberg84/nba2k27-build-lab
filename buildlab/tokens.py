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


# Rows exist for all 20 legal heights, but every token value at height 82 and
# above is zero while the slots field in the same rows stays populated. Across
# 69-81 the count of nonzero-token rows climbs smoothly (689 -> 747) and then
# falls to exactly 0 at 82. That discontinuity is the signature of a capture
# that stopped recording tokens, not of a game rule: it would mean every build
# 6'10" and taller earns no badge tokens from any attribute at any rating.
# Upstream commit 957d009 is the latest and its README does not mention this.
# Treat 82+ as MISSING data, never as zero.
TOKEN_DATA_HEIGHTS = tuple(range(69, 82))


def has_token_data(height_inches):
    """Whether token contribution data is trustworthy at this height."""
    return height_inches in TOKEN_DATA_HEIGHTS


def contribution(height_inches, attribute, rating):
    """Tokens earned per discipline from ONE attribute at this rating.

    Measured with every other attribute at the 25 floor. Six values in
    badges.DISCIPLINE_ORDER. This is a measured fact; see estimate_earned for
    the build-level extrapolation and its caveat.

    Only covers heights 69-81. Rows exist for 82-88 too, but every token
    value there is zero while slots keeps working in the same rows -- a
    capture defect, not a real height effect -- so that range is refused
    rather than answered with a false zero.
    """
    if not has_token_data(height_inches) and 82 <= height_inches <= 88:
        raise KeyError(
            f"token contribution data is not trustworthy at height "
            f"{height_inches}: rows exist but every token value is zero from "
            "height 82 up, while slots stay populated. Treated as missing, not "
            f"as zero. Trustworthy heights are {TOKEN_DATA_HEIGHTS[0]}-"
            f"{TOKEN_DATA_HEIGHTS[-1]}."
        )
    index = _contribution_index()
    key = (height_inches, attribute, rating)
    if key not in index:
        raise KeyError(
            f"no token contribution for height {height_inches}, attribute "
            f"{attribute}, rating {rating}; heights 69-88, attributes 0-20, "
            "ratings 25-99"
        )
    return index[key]


ADDITIVITY_BASIS = (
    "Summing the 21 per-attribute contributions. The upstream README states "
    "the token function is additive across attributes and that summing a "
    "build's 21 rows gives its exact token budget, verified there against "
    "2,048 native vectors. Those vectors are not shipped, so this cannot be "
    "re-checked from the vendored files: locally_verified is False for that "
    "reason, not because the result is doubted."
)


def earned(values, height_inches):
    """Badge tokens a build earns, per discipline.

    Returns a dict with `per_discipline` (6 ints in badges.DISCIPLINE_ORDER),
    `total`, `locally_verified` (always False, see ADDITIVITY_BASIS) and
    `basis`.

    Raises for heights 82 and above: token data is not trustworthy there, and
    silently totalling zero would report that tall builds earn no tokens.
    """
    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")
    totals = [0] * 6
    for attribute, rating in enumerate(values):
        got = contribution(height_inches, attribute, rating)
        totals = [a + b for a, b in zip(totals, got)]
    return {
        "per_discipline": tuple(totals),
        "total": sum(totals),
        "locally_verified": False,
        "basis": ADDITIVITY_BASIS,
    }
