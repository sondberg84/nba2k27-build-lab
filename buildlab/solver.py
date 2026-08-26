"""Find the cheapest legal build meeting a set of goals.

Every requirement in the data is a lower bound, so the cheapest build is the
pointwise maximum of the implied floors, closed under linked attribute
constraints. Nothing is searched over attribute space. The only branching is a
badge tier whose requirement uses OR, and only for badges actually requested.
"""

import itertools

from buildlab import animations, ladders, ovr, reference

# Heights any legal build can have: the union of the five positions' ranges.
MIN_HEIGHT = 69
MAX_HEIGHT = 88


def _best_ceilings(height_inches):
    """Best reachable ceiling per attribute at a height, across legal bodies."""
    return {
        name: animations.max_ceiling_at(height_inches, name)
        for name in reference.attribute_names()
    }


def _merge(options):
    """Pointwise maximum of several floor dicts."""
    merged = {}
    for option in options:
        for attribute, minimum in option.items():
            if minimum > merged.get(attribute, 0):
                merged[attribute] = minimum
    return merged


def solve_at(goal_list, height_inches):
    """Cheapest build meeting every goal at one height.

    Returns a dict with `feasible`, and on success `build` (all 21 attributes),
    `points` (upgrades above the 25 floor), `overall`, and `height_inches`. On
    failure, `reason` explains which goal cannot be met and why.
    """
    per_goal = []
    for goal in goal_list:
        options = goal.floor_options(height_inches)
        if not options:
            return {
                "feasible": False,
                "height_inches": height_inches,
                "reason": (
                    f"{goal.describe()} is not attainable at "
                    f"{height_inches // 12}'{height_inches % 12}"
                ),
            }
        per_goal.append(options)

    ceilings = _best_ceilings(height_inches)
    best = None
    for combination in itertools.product(*per_goal):
        floors = _merge(combination)
        closed = ladders.full_cost_of(floors, height_inches)
        if any(
            minimum > ceilings.get(attribute, 0)
            for attribute, minimum in closed.items()
        ):
            continue
        build = {
            name: max(closed.get(name, 0), ladders.ATTRIBUTE_FLOOR)
            for name in reference.attribute_names()
        }
        points = sum(v - ladders.ATTRIBUTE_FLOOR for v in build.values())
        candidate = {
            "feasible": True,
            "height_inches": height_inches,
            "build": build,
            "points": points,
            "overall": ovr.overall(
                height_inches, [build[n] for n in reference.attribute_names()]
            ),
        }
        if best is None or candidate["points"] < best["points"]:
            best = candidate

    if best is not None:
        return best

    floors = _merge(next(itertools.product(*per_goal)))
    closed = ladders.full_cost_of(floors, height_inches)
    worst = None
    for attribute, minimum in closed.items():
        excess = minimum - ceilings.get(attribute, 0)
        if worst is None or excess > worst[1]:
            worst = (attribute, excess, minimum, ceilings.get(attribute, 0))
    reason = (
        f"needs {worst[0]} {worst[2]} but the ceiling at "
        f"{height_inches // 12}'{height_inches % 12} is {worst[3]}"
    )
    return {"feasible": False, "height_inches": height_inches, "reason": reason}


def solve(goal_list, heights=None):
    """Cheapest build meeting every goal, searched across heights.

    Returns `feasible`, `heights` (every height that works, ascending), `best`
    (the cheapest solve_at result by points, ties broken by lower height), and
    `per_height`. On total failure, `reason` names the goals that conflict.
    """
    candidates = list(heights or range(MIN_HEIGHT, MAX_HEIGHT + 1))
    per_height = {}
    working = []
    for height in candidates:
        outcome = solve_at(goal_list, height)
        per_height[height] = outcome
        if outcome["feasible"]:
            working.append(height)

    if working:
        best = min(
            (per_height[h] for h in working),
            key=lambda r: (r["points"], r["height_inches"]),
        )
        return {
            "feasible": True,
            "heights": working,
            "best": best,
            "per_height": per_height,
        }

    return {
        "feasible": False,
        "heights": [],
        "per_height": per_height,
        "reason": _diagnose(goal_list, candidates),
    }


def _diagnose(goal_list, candidates):
    """Explain why no height works, naming a conflicting pair when there is one."""
    reachable = {}
    for goal in goal_list:
        reachable[goal.describe()] = {h for h in candidates if goal.floor_options(h)}

    empty = [name for name, heights in reachable.items() if not heights]
    if empty:
        return f"{empty[0]} is not attainable at any legal height"

    names = list(reachable)
    for first, second in itertools.combinations(names, 2):
        if not reachable[first] & reachable[second]:
            return f"{first} and {second} cannot coexist: they share no legal height"

    return (
        "no single height satisfies every goal; each is individually attainable "
        "but the attribute ceilings do not allow them together"
    )
