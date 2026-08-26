"""Animation packages: requirements parsed from the NBA2KLab markdown tables."""

import functools
import re

from buildlab import body, reference, sources

REL = "local/animation_requirements.md"

# The markdown column headers, mapped to builder attribute names. Twelve
# distinct attribute columns appear across the 52 families.
COLUMN_ATTRIBUTE = {
    "Ball Handle": "ball_handle",
    "Speed": "speed",
    "Agility": "agility",
    "Mid": "mid_range",
    "3Pt": "three_point",
    "Vertical": "vertical",
    "Dr. Dunk": "driving_dunk",
    "Dr. Layup": "driving_layup",
    "Std Dunk": "standing_dunk",
    "Passing Accuracy": "pass_accuracy",
    "Speed w/ Ball": "speed_with_ball",
    "Post Control": "post_control",
}

# The package name lives under `Package` in most families and `Name` in the
# Motion styles section.
NAME_COLUMNS = ("Package", "Name")

# An em dash means the column carries no requirement for that row.
NO_REQUIREMENT = "—"

HEIGHT_RE = re.compile(r"^(\d+)'(\d+)$")
COUNT_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


def _height(text):
    match = HEIGHT_RE.match(text.strip())
    if not match:
        raise ValueError(f"unparseable height {text!r}")
    return int(match.group(1)) * 12 + int(match.group(2))


def _is_separator(cells):
    return set("".join(cells)) <= set("-: ")


@functools.lru_cache(maxsize=1)
def packages():
    """Every animation package as a dict.

    Keys: `name`, `family`, `section`, `min_height`, `max_height` (both in
    whole inches) and `requirements`, a dict of builder attribute name to
    minimum rating. A package with no attribute requirement has an empty
    requirements dict.
    """
    rows = []
    section = family = header = None
    text = sources.path_for(REL).read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("## "):
            section = COUNT_SUFFIX_RE.sub("", line[3:].strip())
            family = header = None
            continue
        if line.startswith("### "):
            family = COUNT_SUFFIX_RE.sub("", line[4:].strip())
            header = None
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if _is_separator(cells):
            continue
        if header is None:
            header = cells
            continue
        row = dict(zip(header, cells))
        name = ""
        for column in NAME_COLUMNS:
            if row.get(column):
                name = row[column]
                break
        requirements = {}
        for column, attribute in COLUMN_ATTRIBUTE.items():
            value = row.get(column, NO_REQUIREMENT)
            if value and value != NO_REQUIREMENT:
                requirements[attribute] = int(value)
        rows.append(
            {
                "name": name,
                # Motion styles is one flat table with no `###` sub-headings,
                # so its 353 rows have no family of their own. The section is
                # the family in that case, which keeps every row addressable
                # by (family, name) and stops families() sorting None.
                "family": family or section,
                "section": section,
                "min_height": _height(row["Min Height"]),
                "max_height": _height(row["Max Height"]),
                "requirements": requirements,
            }
        )
    return rows


@functools.lru_cache(maxsize=1)
def _by_key():
    return {(r["family"], r["name"]): r for r in packages()}


def by_name(name, family):
    index = _by_key()
    if (family, name) not in index:
        raise KeyError(f"no package {name!r} in family {family!r}")
    return index[(family, name)]


@functools.lru_cache(maxsize=1)
def families():
    return tuple(sorted({r["family"] for r in packages()}))


def _qualifies(row, values, height_inches, name_index):
    if not row["min_height"] <= height_inches <= row["max_height"]:
        return False
    for attribute, minimum in row["requirements"].items():
        if values[name_index[attribute]] < minimum:
            return False
    return True


def available(values, height_inches, family=None):
    """Packages this build can use, optionally filtered to one family."""
    if len(values) != 21:
        raise ValueError(f"expected 21 attribute values, got {len(values)}")
    name_index = {n: i for i, n in enumerate(reference.attribute_names())}
    return [
        row
        for row in packages()
        if (family is None or row["family"] == family)
        and _qualifies(row, values, height_inches, name_index)
    ]


def requirements_of(name, family):
    """Every gate on a package: attribute minimums and the height range."""
    row = by_name(name, family)
    return {
        "requirements": dict(row["requirements"]),
        "min_height": row["min_height"],
        "max_height": row["max_height"],
    }


@functools.lru_cache(maxsize=None)
def max_ceiling_at(height_inches, attribute):
    """Highest ceiling for an attribute across every legal body at a height.

    Scans all legal weight and wingspan combinations at that height. Returns 0
    if no position permits the height at all.
    """
    best = 0
    for position in reference.legal_bodies():
        for entry in position["bodies"]:
            if entry["height_inches"] != height_inches:
                continue
            weights = entry["weight_lb"]
            spans = entry["wingspan_inches"]
            for weight in range(weights[0], weights[1] + 1):
                for wingspan in range(spans[0], spans[1] + 1):
                    caps = body.ceilings(
                        height=height_inches, weight=weight, wingspan=wingspan
                    )
                    if caps[attribute] > best:
                        best = caps[attribute]
    return best


def reachable_at(name, family, height_inches):
    """Whether a package's requirements are physically reachable at a height.

    The stated height range is a necessary condition. This checks the
    sufficient one: that some legal body at this height has a ceiling high
    enough for every attribute the package requires.
    """
    row = by_name(name, family)
    if not row["min_height"] <= height_inches <= row["max_height"]:
        return False
    for attribute, minimum in row["requirements"].items():
        if max_ceiling_at(height_inches, attribute) < minimum:
            return False
    return True


def reachable_range(name, family):
    """The heights where a package is actually attainable.

    Returns `min_height`, `max_height`, `narrower_than_stated`, and
    `blocked_by` — the attribute whose ceiling binds, or None. Both heights are
    None if the package is unreachable at every legal height.
    """
    row = by_name(name, family)
    heights = [
        h
        for h in range(row["min_height"], row["max_height"] + 1)
        if reachable_at(name, family, h)
    ]
    stated_span = row["max_height"] - row["min_height"] + 1
    blocked_by = None
    if len(heights) < stated_span:
        worst = None
        for attribute, minimum in row["requirements"].items():
            shortfall = minimum - max_ceiling_at(row["max_height"], attribute)
            if worst is None or shortfall > worst[1]:
                worst = (attribute, shortfall)
        if worst and worst[1] > 0:
            blocked_by = worst[0]
    return {
        "min_height": heights[0] if heights else None,
        "max_height": heights[-1] if heights else None,
        "narrower_than_stated": len(heights) < stated_span,
        "blocked_by": blocked_by,
    }
