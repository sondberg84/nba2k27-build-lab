"""Compare a build in progress against a target.

Answers the question you have while actually sitting in the builder: how far
off the plan am I, and is anything I have already spent buying nothing.
"""

from buildlab import animations, badges, reference


def _check(values, label):
    if len(values) != 21:
        raise ValueError(f"expected 21 {label} values, got {len(values)}")


def compare(current, target, height_inches):
    """What separates a build in progress from where it is meant to end up.

    Returns `short` (attributes below target, largest gap first), `surplus`
    (above target), `points_remaining` (upgrades still needed), the badge and
    animation counts on each side, `badges_missing` (what the target unlocks
    that the current build does not), and `illegal` / `target_illegal` for
    anything above its ceiling at this height.
    """
    _check(current, "current")
    _check(target, "target")

    names = reference.attribute_names()
    ceilings = {n: animations.max_ceiling_at(height_inches, n) for n in names}

    short, surplus, illegal, target_illegal = [], [], [], []
    for index, name in enumerate(names):
        have, want = current[index], target[index]
        if have > ceilings[name]:
            illegal.append(
                {"attribute": name, "value": have, "ceiling": ceilings[name]}
            )
        if want > ceilings[name]:
            target_illegal.append(
                {"attribute": name, "value": want, "ceiling": ceilings[name]}
            )
        if have < want:
            short.append(
                {
                    "attribute": name,
                    "current": have,
                    "target": want,
                    "gap": want - have,
                }
            )
        elif have > want:
            surplus.append(
                {
                    "attribute": name,
                    "current": have,
                    "target": want,
                    "over": have - want,
                }
            )

    unlocked_now = badges.unlocked(current, height_inches)
    unlocked_target = badges.unlocked(target, height_inches)
    missing = []
    for badge_id, tier in unlocked_target.items():
        if unlocked_now.get(badge_id) != tier:
            missing.append(
                {
                    "badge": badges.by_id(badge_id)["name"],
                    "tier": tier,
                    "have": unlocked_now.get(badge_id),
                }
            )

    return {
        "height_inches": height_inches,
        "short": sorted(short, key=lambda s: -s["gap"]),
        "surplus": sorted(surplus, key=lambda s: -s["over"]),
        "points_remaining": sum(s["gap"] for s in short),
        "points_surplus": sum(s["over"] for s in surplus),
        "badges_current": len(unlocked_now),
        "badges_target": len(unlocked_target),
        "badges_missing": sorted(missing, key=lambda m: m["badge"]),
        "animations_current": len(animations.available(current, height_inches)),
        "animations_target": len(animations.available(target, height_inches)),
        "illegal": illegal,
        "target_illegal": target_illegal,
    }
