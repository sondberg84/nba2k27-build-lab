"""Threshold ladders: what each additional point in an attribute buys."""

import functools

from buildlab import animations, badges, constraints, reference, tables

# Every attribute starts at 25: the tuning export states it as
# AttributePreset[INITIAL].Value[<attribute>]. An implied minimum at or below
# that is already satisfied by an untouched build and is not a cost.
ATTRIBUTE_FLOOR = 25


def _attribute_index(attribute):
    names = reference.attribute_names()
    if attribute not in names:
        raise KeyError(
            f"no builder attribute named {attribute!r}; valid names are {names}"
        )
    return names.index(attribute)


@functools.lru_cache(maxsize=None)
def max_ceiling(attribute, height_inches):
    """Highest reachable value for an attribute at a height, any legal body."""
    _attribute_index(attribute)
    return animations.max_ceiling_at(height_inches, attribute)


@functools.lru_cache(maxsize=None)
def ladder(attribute, height_inches):
    """Every rating at which this attribute unlocks something, ascending.

    Each step is a dict with `rating`, `animations` (list of "family: name")
    and `badges` (list of "badge tier"). Only ratings reachable at this height
    are included: promising an unlock a body cannot reach is worse than
    silence.
    """
    index = _attribute_index(attribute)
    ceiling = max_ceiling(attribute, height_inches)

    steps = {}
    for row in animations.packages():
        if attribute not in row["requirements"]:
            continue
        if not row["min_height"] <= height_inches <= row["max_height"]:
            continue
        minimum = row["requirements"][attribute]
        if minimum > ceiling:
            continue
        steps.setdefault(minimum, {"animations": [], "badges": []})
        steps[minimum]["animations"].append(f"{row['family']}: {row['name']}")

    for badge in badges.definitions():
        if not badges.height_eligible(badge["badge"], height_inches):
            continue
        for tier in badges.TIERS:
            for requirement in badges.requirements_for(badge["badge"], tier):
                if requirement["attribute"] != index:
                    continue
                minimum = requirement["minimum"]
                if minimum > ceiling:
                    continue
                steps.setdefault(minimum, {"animations": [], "badges": []})
                steps[minimum]["badges"].append(f"{badge['name']} {tier}")

    return tuple(
        {
            "rating": rating,
            "animations": tuple(sorted(steps[rating]["animations"])),
            "badges": tuple(sorted(steps[rating]["badges"])),
        }
        for rating in sorted(steps)
    )


def dead_points(attribute, height_inches, rating):
    """How many points at this rating are buying nothing.

    `wasted` counts points above the last unlock reached. `next_unlock_at` is
    the next rating that buys something, or None if there is nothing further.
    """
    steps = ladder(attribute, height_inches)
    reached = [s["rating"] for s in steps if s["rating"] <= rating]
    upcoming = [s["rating"] for s in steps if s["rating"] > rating]
    last = max(reached) if reached else None
    return {
        "wasted": rating - last if last is not None else 0,
        "last_unlock_at": last,
        "next_unlock_at": min(upcoming) if upcoming else None,
    }


def full_cost_of(targets, height_inches):
    """Expand attribute targets to include everything they force.

    Linked attribute constraints mean an attribute cannot be raised alone. The
    constraint graph is fully connected — every attribute is capped relative to
    at least one other at every legal height — so a single target propagates
    transitively until it reaches a fixed point.

    Only implied minimums above ATTRIBUTE_FLOOR are returned. A build starts
    with every attribute at 25, so an implied minimum at or below that costs
    nothing and reporting it would overstate the price.

    Asking for 94 speed with ball at 6'2" really requires twelve attributes,
    led by speed 94, ball handle 89 and agility 79.
    """
    bucket = tables.bucket_for_inches(height_inches)
    to_tuning = reference.TUNING_NAME
    from_tuning = {v: k for k, v in to_tuning.items()}

    resolved = dict(targets)
    changed = True
    while changed:
        changed = False
        for attribute, minimum in list(resolved.items()):
            rules = constraints.rules_for(to_tuning[attribute], bucket)
            for rule in rules:
                partner = from_tuning.get(rule["associated"])
                if partner is None:
                    continue
                needed = minimum - rule["max_delta"]
                if needed > resolved.get(partner, 0):
                    resolved[partner] = needed
                    changed = True
    return {k: v for k, v in resolved.items() if v > ATTRIBUTE_FLOOR}
