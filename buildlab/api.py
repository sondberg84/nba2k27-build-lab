"""JSON-ready views over the engine, for the local web UI.

Pure functions returning plain dicts. No sockets here — that is server.py —
so all of this is testable directly.
"""

from buildlab import (
    animations,
    badges,
    ladders,
    ovr,
    reference,
    solver,
    sources,
    tokens,
)


def meta():
    """Everything the page needs before it can render anything."""
    return {
        "attributes": list(reference.attribute_names()),
        "min_height": solver.MIN_HEIGHT,
        "max_height": solver.MAX_HEIGHT,
        "floor": ladders.ATTRIBUTE_FLOOR,
        "commit": sources.load()["sources"][0]["commit"],
        "families": list(animations.families()),
    }


def _check(values, height_inches):
    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")
    if not solver.MIN_HEIGHT <= height_inches <= solver.MAX_HEIGHT:
        raise ValueError(
            f"height {height_inches} is outside the legal range "
            f"{solver.MIN_HEIGHT}-{solver.MAX_HEIGHT}"
        )


def evaluate(values, height_inches):
    """The main view: everything that changes as you drag a slider."""
    _check(values, height_inches)
    names = reference.attribute_names()

    ceilings = {
        name: animations.max_ceiling_at(height_inches, name) for name in names
    }
    illegal = [
        {"attribute": name, "value": values[i], "ceiling": ceilings[name]}
        for i, name in enumerate(names)
        if values[i] > ceilings[name]
    ]

    unlocked = badges.unlocked(values, height_inches)
    by_tier = {tier: [] for tier in badges.TIERS}
    for badge_id, tier in unlocked.items():
        by_tier[tier].append(badges.by_id(badge_id)["name"])
    for tier in by_tier:
        by_tier[tier].sort()

    if tokens.has_token_data(height_inches):
        earned = tokens.earned(values, height_inches)
        token_view = {
            "available": True,
            "total": earned["total"],
            "per_discipline": list(earned["per_discipline"]),
            "locally_verified": earned["locally_verified"],
        }
    else:
        low = tokens.TOKEN_DATA_HEIGHTS[0]
        high = tokens.TOKEN_DATA_HEIGHTS[-1]
        token_view = {
            "available": False,
            "reason": (
                f"The shipped data records zero tokens for every attribute at "
                f"height {height_inches}, while badge slots stay populated. "
                f"That reads as a capture gap, not a game rule, so it is "
                f"treated as missing rather than as zero. Trustworthy heights "
                f"are {low}-{high} inches."
            ),
        }

    return {
        "height_inches": height_inches,
        "overall": ovr.overall(height_inches, values),
        "detailed": round(ovr.detailed(height_inches, values), 4),
        "archetype": ovr.archetype(height_inches, values),
        "badge_count": len(unlocked),
        "badges_by_tier": by_tier,
        "animation_count": len(animations.available(values, height_inches)),
        "ceilings": ceilings,
        "illegal": illegal,
        "points": sum(max(v - ladders.ATTRIBUTE_FLOOR, 0) for v in values),
        "tokens": token_view,
    }


def ladder(attribute, height_inches):
    """The threshold ladder for one attribute, as plain lists."""
    steps = ladders.ladder(attribute, height_inches)
    return {
        "attribute": attribute,
        "height_inches": height_inches,
        "ceiling": ladders.max_ceiling(attribute, height_inches),
        "steps": [
            {
                "rating": step["rating"],
                "badges": list(step["badges"]),
                "animations": list(step["animations"]),
            }
            for step in steps
        ],
    }
