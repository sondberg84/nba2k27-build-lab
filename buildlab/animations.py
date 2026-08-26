"""Animation packages: requirements parsed from the NBA2KLab markdown tables."""

import functools
import re

from buildlab import sources

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
                "family": family,
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
