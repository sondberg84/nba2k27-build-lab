"""Evaluate a build somebody else proposed."""

from buildlab import animations, badges, ladders, ovr, reference


def critique(values, height_inches):
    """Full report on a proposed build.

    Returns `overall`, `archetype`, `badges` (id -> tier), `waste` (attributes
    with points buying nothing), `illegal` (attributes above their ceiling) and
    `unspecified` (attributes still at the floor, which a transcript probably
    just did not mention).
    """
    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")

    names = reference.attribute_names()
    illegal = []
    waste = []
    unspecified = []
    for index, name in enumerate(names):
        value = values[index]
        ceiling = animations.max_ceiling_at(height_inches, name)
        if value > ceiling:
            illegal.append({"attribute": name, "value": value, "ceiling": ceiling})
            continue
        if value <= ladders.ATTRIBUTE_FLOOR:
            unspecified.append(name)
            continue
        dead = ladders.dead_points(name, height_inches, value)
        if dead["wasted"] > 0:
            waste.append(
                {
                    "attribute": name,
                    "value": value,
                    "wasted": dead["wasted"],
                    "last_unlock_at": dead["last_unlock_at"],
                    "next_unlock_at": dead["next_unlock_at"],
                }
            )

    return {
        "height_inches": height_inches,
        "overall": ovr.overall(height_inches, values),
        "archetype": ovr.archetype(height_inches, values),
        "badges": badges.unlocked(values, height_inches),
        "waste": sorted(waste, key=lambda w: -w["wasted"]),
        "illegal": illegal,
        "unspecified": unspecified,
    }


def check_claims(values, height_inches, claims):
    """Check stated badge claims against what the build actually reaches.

    `claims` is a list of (badge_name, tier). Each result carries `badge`,
    `claimed`, `holds` and, when it does not hold, `actual` — the tier the
    build really reaches, or None.
    """
    checked = []
    for badge_name, tier in claims:
        badge = badges.by_name(badge_name)
        actual = badges.best_tier(badge["badge"], values, height_inches)
        holds = actual == tier
        entry = {"badge": badge_name, "claimed": tier, "holds": holds}
        if not holds:
            entry["actual"] = actual
        checked.append(entry)
    return checked
