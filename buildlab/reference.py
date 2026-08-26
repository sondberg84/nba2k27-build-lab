"""Builder reference data and the attribute name mapping."""

import functools

from buildlab import sources

TUNING_NAME = {
    "close_shot": "ShotClose",
    "driving_layup": "DrivingLayup",
    "driving_dunk": "DrivingDunk",
    "standing_dunk": "StandingDunk",
    "post_control": "PostControl",
    "mid_range": "ShotMidrange",
    "three_point": "ShotThree",
    "free_throw": "ShotFreeThrow",
    "pass_accuracy": "PassAccuracy",
    "ball_handle": "BallControl",
    "speed_with_ball": "SpeedWithBall",
    "interior_defense": "InteriorDefense",
    "perimeter_defense": "PerimeterDefense",
    "steal": "Steal",
    "block": "Block",
    "offensive_rebound": "ReboundOffense",
    "defensive_rebound": "ReboundDefense",
    "speed": "Speed",
    "agility": "Agility",
    "strength": "Strength",
    "vertical": "Vertical",
}


@functools.lru_cache(maxsize=1)
def attributes():
    return sorted(sources.rows_for("reference/attributes.json"), key=lambda a: a["index"])


@functools.lru_cache(maxsize=1)
def attribute_names():
    return tuple(a["name"] for a in attributes())


@functools.lru_cache(maxsize=1)
def tuning_order():
    """Tuning identifiers in builder attribute-index order."""
    return tuple(TUNING_NAME[name] for name in attribute_names())


@functools.lru_cache(maxsize=1)
def legal_bodies():
    return sources.rows_for("bodies/legal_bodies.json")
