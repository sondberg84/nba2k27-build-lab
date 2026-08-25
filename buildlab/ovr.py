"""Overall rating: archetype selection, the float overall, and the displayed integer.

The formula, in full:

    for each of the 15 archetypes at this height bucket
        w[i] = HeightBasedAttributeWeight[HEIGHT_b][PLAYERTYPE_p][attr i]
        s[i] = AttributeRatingWeightScale[attr i][values[i]]   (1.0 below 75)
        pre  = sum(w[i] * s[i] * values[i]) / sum(w[i] * s[i])
        raw  = HeightBasedOverallLerp[HEIGHT_b] applied to pre
    winner   = the archetype with the largest raw
    detailed = min(raw of the winner, display cap)
    overall  = floor(detailed)

`pre` is a weighted *average*, not a weighted sum: the rating scale multiplies
the weight and the denominator is the resulting scaled weight sum. See
buildlab.archetypes.scaled_score, and docs/superpowers/notes/ovr-derivation.md
for the derivation and its evidence.

Every term is a named tuning key except the display cap; see DISPLAY_CAP.
"""

import math
import struct

from buildlab import archetypes, tables

MAX_RATING = 99


def _float32_predecessor(value):
    bits = struct.unpack("I", struct.pack("f", value))[0]
    return struct.unpack("f", struct.pack("I", bits - 1))[0]


# The engine holds a sub-maximal build one float32 ULP below 99 so the builder
# displays 98 until the build is complete -- the dataset calls this "the
# 98-to-99 completion edge". This constant is NOT traceable to a tuning key; it
# is read off the goldens, where every clamped row records exactly
# 98.99999237060547 (uniform ratings 84-98, and mixed_vectors sample 25).
# No ordering of the bucket-11 lerp arithmetic produces it in float32, so it is
# an engine constant rather than a rounding artefact of the formula above.
DISPLAY_CAP = _float32_predecessor(float(MAX_RATING))


def _cap_for(values):
    """The ceiling applied to the float overall.

    Lifted to a clean 99.0 only for a fully maxed vector. That predicate rests
    on a single recorded row (uniform rating 99, the only golden that reaches
    99.0), so it is the deliberately conservative reading; the notes record the
    alternative and why the two cannot be told apart from this dataset.
    """
    return float(MAX_RATING) if min(values) >= MAX_RATING else DISPLAY_CAP


def _raw(bucket, player_type, values):
    """Post-lerp overall for one archetype, before the display cap."""
    return tables.lerp(bucket, archetypes.scaled_score(bucket, player_type, values))


def archetype(height_inches, values):
    """Winning archetype index for this build: a PLAYERTYPE slot, 0-14."""
    return archetypes.select(tables.bucket_for_inches(height_inches), values)


def detailed(height_inches, values):
    """The float overall the builder computes, after the display cap."""
    bucket = tables.bucket_for_inches(height_inches)
    winner = archetypes.select(bucket, values)
    return min(_raw(bucket, winner, values), _cap_for(values))


def overall(height_inches, values):
    """The integer overall the builder displays."""
    return math.floor(detailed(height_inches, values))
