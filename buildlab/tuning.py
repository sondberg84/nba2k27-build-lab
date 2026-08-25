"""Reader for the named key/value tuning export."""

import functools

from buildlab import sources

REL = "tuning/progression_attributes.txt"


@functools.lru_cache(maxsize=1)
def load():
    """Return the tuning export as a flat dict of key -> raw string value."""
    table = {}
    path = sources.path_for(REL)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("DataPath"):
                continue
            key, sep, value = line.partition(",")
            if not sep:
                continue
            table[key.strip()] = value.strip()
    return table
