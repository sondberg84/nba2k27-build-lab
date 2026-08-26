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


def cost_of_loadout(loadout, height_inches):
    """Total tokens to equip a {badge_id: tier} loadout at this height."""
    total = 0
    for badge_id, tier in loadout.items():
        if is_unreachable_tier(tier):
            raise ValueError(
                f"badge {badge_id} at tier {tier!r} cannot be equipped at build "
                "creation; legend comes only from a Max Plus 2 fuse slot"
            )
        total += cost_for(badge_id, tier, height_inches)
    return total
