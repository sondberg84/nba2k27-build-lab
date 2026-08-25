"""Typed lookup tables derived from the tuning export."""

import functools
import re

from buildlab import reference, tuning

WEIGHT_RE = re.compile(
    r"^HeightBasedAttributeWeight\[HEIGHT_(\d+)\]\[PLAYERTYPE_(\d+)\]"
    r"\[PLAYERDATA_ATTRIBUTE_(\w+)Ability\]$"
)
# The tuning file declares a bare AttributeRatingWeightScale default of 1.0
# alongside the 550 per-(attribute, rating) rows, which is why scale_for()
# returns 1.0 for ratings below the table's floor of 75.
SCALE_RE = re.compile(
    r"^AttributeRatingWeightScale\[PLAYERDATA_ATTRIBUTE_(\w+)Ability\]\[(\d+)\]$"
)
LERP_RE = re.compile(r"^HeightBasedOverallLerp\[HEIGHT_(\d+)\]\.Value\[(\d)\]\[(\d)\]$")
BUCKET_RE = re.compile(r"^HeightInWholeInches\[HEIGHT_(\d+)\]$")


@functools.lru_cache(maxsize=1)
def height_buckets():
    """Bucket index -> whole inches."""
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = BUCKET_RE.match(key)
        if match:
            out[int(match.group(1))] = int(value)
    return out


def bucket_for_inches(inches):
    for bucket, value in height_buckets().items():
        if value == inches:
            return bucket
    raise KeyError(f"no height bucket for {inches} inches")


@functools.lru_cache(maxsize=1)
def _weight_index():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = WEIGHT_RE.match(key)
        if match:
            bucket, player_type, attr = match.groups()
            out[(int(bucket), int(player_type), attr)] = float(value)
    return out


@functools.lru_cache(maxsize=1)
def player_types():
    return tuple(sorted({pt for _, pt, _ in _weight_index()}))


@functools.lru_cache(maxsize=1)
def weight_buckets():
    """Height buckets the weight table covers: 5-24, i.e. 69-88 inches.

    This is exactly the union of every position's legal height range. Heights
    outside it carry no weight data because no build can reach them.
    """
    return tuple(sorted({bucket for bucket, _, _ in _weight_index()}))


@functools.lru_cache(maxsize=None)
def weights(bucket, player_type):
    """21 weights in builder attribute-index order.

    An attribute absent from a row is an implicit 0.0, not an error: 29 of the
    300 rows omit StandingDunk at buckets 5-8, and those rows already sum to
    ~100 without it. A bucket with no data at all is an error, because it means
    the caller asked about a height no build can have.
    """
    covered = weight_buckets()
    if bucket not in covered:
        raise KeyError(
            f"no weight data for height bucket {bucket}; "
            f"covered buckets are {covered[0]}-{covered[-1]}"
        )
    index = _weight_index()
    return tuple(
        index.get((bucket, player_type, attr), 0.0)
        for attr in reference.tuning_order()
    )


@functools.lru_cache(maxsize=1)
def rating_scale():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = SCALE_RE.match(key)
        if match:
            out[(match.group(1), int(match.group(2)))] = float(value)
    return out


def scale_for(attr, rating):
    """Rating weight scale, defaulting to 1.0 below the table's floor of 75."""
    return rating_scale().get((attr, rating), 1.0)


@functools.lru_cache(maxsize=1)
def _lerp_index():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = LERP_RE.match(key)
        if match:
            bucket, i, j = (int(g) for g in match.groups())
            out[(bucket, i, j)] = float(value)
    return out


def lerp_points(bucket):
    """((x0, x1), (y0, y1)) for the overall display curve at this height."""
    index = _lerp_index()
    return (
        (index[(bucket, 0, 0)], index[(bucket, 0, 1)]),
        (index[(bucket, 1, 0)], index[(bucket, 1, 1)]),
    )


def lerp(bucket, value):
    (x0, x1), (y0, y1) = lerp_points(bucket)
    return y0 + (value - x0) / (x1 - x0) * (y1 - y0)
