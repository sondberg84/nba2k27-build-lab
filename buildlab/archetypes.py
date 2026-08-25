"""Archetype definitions, eligibility minimums and selection.

The tuning export names 12 archetypes via DataPerArchetype, but
HeightBasedAttributeWeight carries 15 distinct PLAYERTYPE weight vectors.
No key family other than HeightBasedAttributeWeight mentions PLAYERTYPE, and
nothing in the vendored data maps an archetype name to a PLAYERTYPE index, so
minimums() cannot currently be applied to a selected archetype index.
"""

import functools
import re

from buildlab import reference, tables, tuning

MIN_RE = re.compile(
    r"^DataPerArchetype\[(\w+)\]\.MinMaxValuePerAttribute\[(\w+)\]\[(\d)\]$"
)


@functools.lru_cache(maxsize=1)
def _minmax_index():
    table = tuning.load()
    out = {}
    for key, value in table.items():
        match = MIN_RE.match(key)
        if match:
            name, attr, slot = match.groups()
            out[(name, attr, int(slot))] = int(value)
    return out


@functools.lru_cache(maxsize=1)
def names():
    return tuple(sorted({name for name, _, _ in _minmax_index()}))


@functools.lru_cache(maxsize=1)
def minimums():
    """Archetype name -> 21 minimum attribute values in builder index order."""
    index = _minmax_index()
    out = {}
    for name in names():
        out[name] = tuple(
            index.get((name, attr, 0), 0) for attr in reference.tuning_order()
        )
    return out


def raw_score(bucket, player_type, values):
    """Plain weighted sum over the 21 attributes, scaled to a 0-99 range."""
    weights = tables.weights(bucket, player_type)
    return sum(w * v for w, v in zip(weights, values)) / 100.0


def select_baseline(bucket, values):
    """Archetype index by plain weighted argmax. Correct on 207/256 goldens."""
    return max(tables.player_types(), key=lambda pt: raw_score(bucket, pt, values))


def scaled_score(bucket, player_type, values):
    """Pre-lerp overall for one archetype: sum(w*s*v) / sum(w*s).

    `w` is HeightBasedAttributeWeight for this (height bucket, archetype) and
    `s` is AttributeRatingWeightScale at each attribute's own rating, which is
    1.0 below the scale table's floor of 75. The denominator is the actual
    scaled weight sum, not a nominal 100: the engine reports a weighted
    *average*, so a rating that carries a large scale pulls the average toward
    itself rather than simply adding more.

    The uniform_ratings goldens pin this down. With every attribute at rating
    r the renormalised average is exactly r for every archetype, and the
    recorded pre-lerp values are exactly r across the whole 25-83 range while
    the winning archetype wanders arbitrarily from row to row -- which is what
    an exact 15-way tie looks like. Dividing by 100 instead reproduces neither.
    """
    weights = tables.weights(bucket, player_type)
    scales = [
        tables.scale_for(attr, value)
        for attr, value in zip(reference.tuning_order(), values)
    ]
    numerator = sum(w * s * v for w, s, v in zip(weights, scales, values))
    denominator = sum(w * s for w, s in zip(weights, scales))
    return numerator / denominator


def select(bucket, values):
    """Winning archetype index: argmax of scaled_score. Exact on all 256 goldens.

    The engine picks the archetype that maximises the same number it goes on to
    report, so selection needs no separate rule once the score is right.
    """
    return max(
        tables.player_types(), key=lambda pt: scaled_score(bucket, pt, values)
    )
