"""Command line entry point."""

import argparse

from buildlab import (
    animations as animations_mod,
    badges as badges_mod,
    critique as critique_mod,
    goals as goals_mod,
    ladders,
    ovr,
    reference,
    solver,
    tokens,
)


def _ft(inches):
    """Whole inches back to the feet-inches form the CLI accepts."""
    return f"{inches // 12}-{inches % 12}"


def parse_height(text):
    feet, _, inches = text.partition("-")
    return int(feet) * 12 + int(inches)


def _eval(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    print(f"HEIGHT     {args.height}  ({height} in)")
    print(f"OVERALL    {ovr.overall(height, values)}")
    print(f"ARCHETYPE  {ovr.archetype(height, values)}")
    print(f"DETAILED   {ovr.detailed(height, values):.6f}")
    print()
    for name, value in zip(reference.attribute_names(), values):
        print(f"  {name:<20} {value}")
    return 0


def _badges(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    unlocked = badges_mod.unlocked(values, height)

    print(f"HEIGHT    {args.height}  ({height} in)")
    print(f"OVERALL   {ovr.overall(height, values)}")
    print(f"UNLOCKED  {len(unlocked)} badges")
    print()

    by_tier = {tier: [] for tier in badges_mod.TIERS}
    for badge_id, tier in unlocked.items():
        by_tier[tier].append(badges_mod.by_id(badge_id)["name"])
    for tier in reversed(badges_mod.TIERS):
        names = sorted(by_tier[tier])
        if not names:
            continue
        print(f"  {tier}:")
        for name in names:
            cost = tokens.cost_for(badges_mod.by_name(name)["badge"], tier, height)
            print(f"    {name:<28} {cost} tokens")
    print()

    if not tokens.has_token_data(height):
        low, high = tokens.TOKEN_DATA_HEIGHTS[0], tokens.TOKEN_DATA_HEIGHTS[-1]
        print("TOKENS EARNED  unavailable at this height")
        print(
            f"  The shipped data records zero tokens for every attribute at "
            f"height {height}, while badge slots stay populated. That reads as "
            f"a capture gap, not a game rule, so it is treated as missing "
            f"rather than as zero. Trustworthy heights are {low}-{high} in."
        )
        return 0

    earned = tokens.earned(values, height)
    print(f"TOKENS EARNED  {earned['total']}")
    for discipline, amount in zip(
        badges_mod.DISCIPLINE_ORDER, earned["per_discipline"]
    ):
        print(f"    {discipline:<12} {amount}")
    print()
    print(f"  BASIS: {earned['basis']}")
    return 0


def _animations(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    rows = animations_mod.available(values, height, family=args.family)
    print(f"HEIGHT     {args.height}  ({height} in)")
    print(f"AVAILABLE  {len(rows)} packages")
    print()
    by_family = {}
    for row in rows:
        by_family.setdefault(row["family"], []).append(row["name"])
    for family in sorted(by_family):
        print(f"  {family}:")
        for name in sorted(by_family[family]):
            print(f"    {name}")
    return 0


def _ladder(args):
    height = parse_height(args.height)
    try:
        steps = ladders.ladder(args.attribute, height)
    except KeyError as error:
        print(f"error: {error}")
        return 2
    ceiling = ladders.max_ceiling(args.attribute, height)
    print(f"LADDER  {args.attribute} at {args.height}  (ceiling {ceiling})")
    print()
    previous = None
    for step in steps:
        if previous is not None and step["rating"] - previous > 1:
            gap = step["rating"] - previous - 1
            print(f"        ({gap} point{'s' if gap > 1 else ''} buying nothing)")
        unlocks = list(step["badges"]) + list(step["animations"])
        head = unlocks[0]
        if len(unlocks) > 4:
            head = f"{unlocks[0]}  (+{len(unlocks) - 1} more)"
            unlocks = unlocks[:1]
        print(f"  {step['rating']:>3}  {head}")
        for extra in unlocks[1:]:
            print(f"       {extra}")
        previous = step["rating"]
    return 0


def _reachability(args):
    families = animations_mod.families()
    if args.family is not None and args.family not in families:
        print(f"error: no family named {args.family!r}")
        return 2
    rows = [
        row
        for row in animations_mod.packages()
        if row["requirements"]
        and (args.family is None or row["family"] == args.family)
    ]
    narrowed = []
    for row in rows:
        real = animations_mod.reachable_range(row["name"], row["family"])
        if real["narrower_than_stated"]:
            narrowed.append((row, real))
    print(f"CHECKED    {len(rows)} packages with attribute requirements")
    print(
        f"NARROWED   {len(narrowed)} are blocked by ceilings inside their "
        "stated height range"
    )
    print()
    for row, real in sorted(
        narrowed, key=lambda pair: pair[0]["family"] + pair[0]["name"]
    ):
        stated = f"{_ft(row['min_height'])} to {_ft(row['max_height'])}"
        if real["min_height"] is None:
            actual = "never reachable"
        else:
            actual = f"{_ft(real['min_height'])} to {_ft(real['max_height'])}"
        print(f"  {row['family']}: {row['name']}")
        print(f"    stated {stated}   actually {actual}   blocked by {real['blocked_by']}")
    return 0


def _parse_goals(args):
    """Turn --attribute/--badge/--animation strings into Goal objects."""
    built = []
    for spec in args.attribute or []:
        name, sep, minimum = spec.partition("=")
        if not sep or not minimum.strip().isdigit():
            raise ValueError(f"--attribute wants name=value, got {spec!r}")
        built.append(goals_mod.AttributeGoal(name.strip(), int(minimum)))
    for spec in args.badge or []:
        name, sep, tier = spec.partition("=")
        if not sep:
            raise ValueError(f"--badge wants name=tier, got {spec!r}")
        built.append(goals_mod.BadgeGoal(name.strip(), tier.strip()))
    for spec in args.animation or []:
        family, sep, name = spec.partition(":")
        if not sep:
            raise ValueError(f"--animation wants Family:Name, got {spec!r}")
        built.append(goals_mod.AnimationGoal(name.strip(), family.strip()))
    return built


def _solve(args):
    try:
        goal_list = _parse_goals(args)
    except ValueError as error:
        print(f"error: {error}")
        return 2
    if not goal_list:
        print("error: give at least one --attribute, --badge or --animation goal")
        return 2

    heights = None
    if args.height is not None:
        heights = [parse_height(args.height)]

    try:
        result = solver.solve(goal_list, heights=heights)
    except (KeyError, ValueError) as error:
        print(f"error: {error}")
        return 2

    print("GOALS")
    for goal in goal_list:
        print(f"  {goal.describe()}")
    print()

    if not result["feasible"]:
        print("NOT FEASIBLE")
        print(f"  {result['reason']}")
        return 0

    best = result["best"]
    low, high = result["heights"][0], result["heights"][-1]
    print(f"FEASIBLE   {_ft(low)} to {_ft(high)}")
    print(
        f"CHEAPEST   {_ft(best['height_inches'])}   "
        f"{best['points']} upgrade points   overall {best['overall']}"
    )
    print()
    for name in reference.attribute_names():
        value = best["build"][name]
        if value > ladders.ATTRIBUTE_FLOOR:
            print(f"  {name:<20} {value}")
    return 0


def _critique(args):
    values = [int(v) for v in args.values.split(",")]
    if len(values) != 21:
        print(f"error: expected 21 attribute values, got {len(values)}")
        return 2
    height = parse_height(args.height)
    report = critique_mod.critique(values, height)

    print(f"HEIGHT     {args.height}  ({height} in)")
    print(f"OVERALL    {report['overall']}   archetype {report['archetype']}")
    print(f"BADGES     {len(report['badges'])} unlocked")
    print()

    if report["illegal"]:
        print("ABOVE THE CEILING — this build cannot be made:")
        for entry in report["illegal"]:
            print(
                f"  {entry['attribute']:<20} {entry['value']} "
                f"but the ceiling here is {entry['ceiling']}"
            )
        print()

    total_wasted = sum(entry["wasted"] for entry in report["waste"])
    print(f"WASTED     {total_wasted} points buying nothing")
    for entry in report["waste"]:
        nxt = entry["next_unlock_at"]
        tail = f", next unlock at {nxt}" if nxt is not None else ", nothing further"
        print(
            f"  {entry['attribute']:<20} {entry['value']} "
            f"({entry['wasted']} wasted{tail})"
        )
    print()

    if report["unspecified"]:
        print(f"AT THE FLOOR  {len(report['unspecified'])} attributes")
        print(f"  {', '.join(report['unspecified'])}")
        print()

    if args.claim:
        claims = []
        for spec in args.claim:
            name, sep, tier = spec.partition("=")
            if not sep:
                print(f"error: --claim wants name=tier, got {spec!r}")
                return 2
            claims.append((name.strip(), tier.strip()))
        print("CLAIMS")
        for checked in critique_mod.check_claims(values, height, claims):
            if checked["holds"]:
                print(f"  {checked['badge']} {checked['claimed']}  holds")
            else:
                actual = checked.get("actual") or "nothing"
                print(
                    f"  {checked['badge']} {checked['claimed']}  "
                    f"does not hold — actually reaches {actual}"
                )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="buildlab")
    sub = parser.add_subparsers(dest="command", required=True)
    ev = sub.add_parser("eval", help="evaluate a full attribute vector")
    ev.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    ev.add_argument("--values", required=True, help="21 comma-separated ratings")
    ev.set_defaults(func=_eval)
    bd = sub.add_parser("badges", help="show badges a build unlocks")
    bd.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    bd.add_argument("--values", required=True, help="21 comma-separated ratings")
    bd.set_defaults(func=_badges)

    an = sub.add_parser("animations", help="show animations a build can use")
    an.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    an.add_argument("--values", required=True, help="21 comma-separated ratings")
    an.add_argument("--family", default=None, help="restrict to one family")
    an.set_defaults(func=_animations)

    la = sub.add_parser("ladder", help="show what each point in an attribute buys")
    la.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    la.add_argument("--attribute", required=True, help="builder attribute name")
    la.set_defaults(func=_ladder)

    rc = sub.add_parser(
        "reachability",
        help="animations blocked by ceilings inside their stated height range",
    )
    rc.add_argument("--family", default=None, help="restrict to one family")
    rc.set_defaults(func=_reachability)

    sv = sub.add_parser("solve", help="find the cheapest build meeting goals")
    sv.add_argument("--attribute", action="append", help="name=value, repeatable")
    sv.add_argument("--badge", action="append", help="name=tier, repeatable")
    sv.add_argument("--animation", action="append", help="Family:Name, repeatable")
    sv.add_argument("--height", default=None, help="fix the height, e.g. 6-3")
    sv.set_defaults(func=_solve)

    cr = sub.add_parser("critique", help="evaluate a build somebody proposed")
    cr.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    cr.add_argument("--values", required=True, help="21 comma-separated ratings")
    cr.add_argument("--claim", action="append", help="name=tier to check, repeatable")
    cr.set_defaults(func=_critique)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
