"""Command line entry point."""

import argparse

from buildlab import ovr, reference


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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="buildlab")
    sub = parser.add_subparsers(dest="command", required=True)
    ev = sub.add_parser("eval", help="evaluate a full attribute vector")
    ev.add_argument("--height", required=True, help="feet-inches, e.g. 6-3")
    ev.add_argument("--values", required=True, help="21 comma-separated ratings")
    ev.set_defaults(func=_eval)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
