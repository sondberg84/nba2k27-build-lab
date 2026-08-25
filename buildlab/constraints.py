"""Linked attribute constraints: per-height caps relative to other attributes."""

import functools
import re

from buildlab import tuning

RULE_RE = re.compile(
    r"^AssociatedAttributeConstraints\[(\w+)\]\[HEIGHT_(\d+)\]\[(\d+)\]\.(\w+)$"
)


@functools.lru_cache(maxsize=1)
def load():
    """(attribute, height_bucket) -> list of {associated, max_delta}."""
    table = tuning.load()
    staged = {}
    for key, value in table.items():
        match = RULE_RE.match(key)
        if not match:
            continue
        attr, bucket, slot, field = match.groups()
        entry = staged.setdefault((attr, int(bucket)), {}).setdefault(int(slot), {})
        if field == "AssociatedAttribute":
            entry["associated"] = value
        elif field == "MaxDelta":
            # int() so that a shipped "0" survives as a hard lock rather than
            # being treated as absent.
            entry["max_delta"] = int(value)

    out = {}
    for pair, slots in staged.items():
        out[pair] = [slots[slot] for slot in sorted(slots) if "associated" in slots[slot]]
    return out


def rules_for(attr, bucket):
    return load().get((attr, bucket), [])


def effective_ceiling(attr, bucket, values, hard_ceiling):
    """Lowest of the body ceiling and every linked-attribute cap."""
    ceiling = hard_ceiling
    for rule in rules_for(attr, bucket):
        associated = values.get(rule["associated"])
        if associated is None:
            continue
        ceiling = min(ceiling, associated + rule["max_delta"])
    return ceiling
