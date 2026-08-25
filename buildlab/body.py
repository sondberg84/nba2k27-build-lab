"""Body legality checks and the attribute ceiling formula.

ceiling = clamp(round(25 + 74 * height_mult * weight_mult * wingspan_mult), 25, 99)

height_mult is a direct per-height lookup. weight_mult and wingspan_mult are
each linearly interpolated between the two endpoint rows the tuning export
ships for that height (its legal min and max weight/wingspan).
"""

import functools
import re

from buildlab import reference, tables, tuning

HEIGHT_MULT_RE = re.compile(
    r"^PlayerRestrictions\[NBA\]\.HeightMultiplier\[HEIGHT_(\d+)\]\[(\w+)\]$"
)
WEIGHT_HEIGHT_RE = re.compile(
    r"^PlayerRestrictions\[NBA\]\.WeightMultiplier\[(\d+)\]\.HeightInInches$"
)
WEIGHT_VALUE_RE = re.compile(
    r"^PlayerRestrictions\[NBA\]\.WeightMultiplier\[(\d+)\]\.Weight$"
)
WEIGHT_MULT_RE = re.compile(
    r"^PlayerRestrictions\[NBA\]\.WeightMultiplier\[(\d+)\]\.Multiplier\[(\w+)\]$"
)
WINGSPAN_HEIGHT_RE = re.compile(
    r"^PlayerRestrictions\[NBA\]\.WingspanMultiplier\[(\d+)\]\.HeightInInches$"
)
WINGSPAN_VALUE_RE = re.compile(
    r"^PlayerRestrictions\[NBA\]\.WingspanMultiplier\[(\d+)\]\.WingspanInInches$"
)
WINGSPAN_MULT_RE = re.compile(
    r"^PlayerRestrictions\[NBA\]\.WingspanMultiplier\[(\d+)\]\.Multiplier\[(\w+)\]$"
)


@functools.lru_cache(maxsize=1)
def _height_multipliers():
    """(HEIGHT_bucket, tuning attribute) -> multiplier."""
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = HEIGHT_MULT_RE.match(key)
        if match:
            bucket, attr = match.groups()
            out[(int(bucket), attr)] = float(value)
    return out


def _range_index(height_re, value_re, mult_re):
    """Build height -> sorted [(value, {attr: multiplier}), ...] (endpoints).

    Rows are grouped by row index, then bucketed by the height each row
    declares. A height with no rows is simply absent from the returned dict
    rather than raising, so callers can decide how to handle it.
    """
    table = tuning.load()
    rows = {}
    for key, value in table.items():
        match = height_re.match(key)
        if match:
            rows.setdefault(int(match.group(1)), {})["height"] = int(value)
            continue
        match = value_re.match(key)
        if match:
            rows.setdefault(int(match.group(1)), {})["value"] = float(value)
            continue
        match = mult_re.match(key)
        if match:
            index, attr = match.groups()
            rows.setdefault(int(index), {}).setdefault("mult", {})[attr] = float(
                value
            )

    by_height = {}
    for index, row in rows.items():
        height = row.get("height")
        if not height:
            # Two padding shapes show up in practice: rows that declare
            # HeightInInches 0, and rows that carry no HeightInInches key at
            # all. Both are inert: every multiplier on them is zero. Assert
            # that rather than assume it, so a future data refresh that
            # introduces a real row with a missing height fails loudly
            # instead of silently vanishing here.
            if any(row.get("mult", {}).values()):
                raise ValueError(
                    f"skipping row {index} with no height but non-zero "
                    "multipliers; the padding convention has changed"
                )
            continue
        by_height.setdefault(height, []).append((row["value"], row["mult"]))

    return {
        height: sorted(pairs, key=lambda pair: pair[0])
        for height, pairs in by_height.items()
    }


@functools.lru_cache(maxsize=1)
def _weight_index():
    return _range_index(WEIGHT_HEIGHT_RE, WEIGHT_VALUE_RE, WEIGHT_MULT_RE)


@functools.lru_cache(maxsize=1)
def _wingspan_index():
    return _range_index(WINGSPAN_HEIGHT_RE, WINGSPAN_VALUE_RE, WINGSPAN_MULT_RE)


def _interpolate(pairs, value, attr):
    """Linear interpolation of `attr`'s multiplier at `value` between endpoints."""
    if len(pairs) == 1:
        return pairs[0][1][attr]
    (v0, m0), (v1, m1) = pairs[0], pairs[-1]
    if v1 == v0:
        return m0[attr]
    t = (value - v0) / (v1 - v0)
    return m0[attr] + t * (m1[attr] - m0[attr])


def _position_record(position):
    for record in reference.legal_bodies():
        if record["position"] == position:
            return record
    return None


def _body_row(position, height):
    record = _position_record(position)
    if record is None:
        return None
    for row in record["bodies"]:
        if row["height_inches"] == height:
            return row
    return None


def is_legal(position, height, weight, wingspan):
    """Whether this position/height/weight/wingspan combination is a real body."""
    row = _body_row(position, height)
    if row is None:
        return False
    weight_lo, weight_hi = row["weight_lb"]
    wingspan_lo, wingspan_hi = row["wingspan_inches"]
    return weight_lo <= weight <= weight_hi and wingspan_lo <= wingspan <= wingspan_hi


def ceilings(height, weight, wingspan):
    """Attribute ceilings for this height/weight/wingspan, keyed by snake_case name.

    Assumes a legal body (see is_legal): the height must exist in the tuning
    tables, or this raises KeyError. A weight or wingspan outside its row's
    legal range is not rejected here — it is linearly extrapolated.
    """
    bucket = tables.bucket_for_inches(height)
    height_mult = _height_multipliers()
    weight_rows = _weight_index().get(height)
    wingspan_rows = _wingspan_index().get(height)
    if weight_rows is None:
        raise KeyError(f"no weight multiplier rows for height {height}")
    if wingspan_rows is None:
        raise KeyError(f"no wingspan multiplier rows for height {height}")

    result = {}
    for name, attr in zip(reference.attribute_names(), reference.tuning_order()):
        key = (bucket, attr)
        if key not in height_mult:
            # HeightMultiplier omits StandingDunk at buckets 5-8 (69-72 in),
            # the only gap in the whole table. This is the same pattern as
            # HeightBasedAttributeWeight's omission of StandingDunk at those
            # same four buckets (tables.weights), where the agreed reading is
            # an implicit weight of 0.0: the attribute is not usable at these
            # heights. There is no answer key for buckets 5-8 -
            # attribute_caps_sample.json covers only bucket 11 - so 25 (the
            # formula's own clamp floor) is a reasoned inference from that
            # parallel omission, not a verified value. If a future probe
            # captures caps at a short height, check this first.
            result[name] = 25
            continue
        h_mult = height_mult[key]
        w_mult = _interpolate(weight_rows, weight, attr)
        s_mult = _interpolate(wingspan_rows, wingspan, attr)
        raw = 25 + 74 * h_mult * w_mult * s_mult
        result[name] = min(99, max(25, round(raw)))
    return result
