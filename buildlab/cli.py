"""Command line entry point."""

import argparse

from buildlab import badges as badges_mod, ovr, reference, tokens


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
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
