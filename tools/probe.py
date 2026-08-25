"""Formula-discovery harness. Reports match rates against the golden vectors.

Run it directly to see the full derivation ladder: every hypothesis that was
tried, in the order it was tried, with the baseline first. The last line is the
formula that ships in buildlab/ovr.py.
"""

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from buildlab import (  # noqa: E402
    archetypes,
    body,
    ovr,
    reference,
    sources,
    tables,
    tuning,
)

BUCKET = 11  # golden vectors use the 6'3 reference body


def golden():
    payload = json.loads(
        sources.path_for("overall/mixed_vectors.json").read_text(encoding="utf-8")
    )
    return payload["data"]


def uniform():
    payload = json.loads(
        sources.path_for("overall/uniform_ratings.json").read_text(encoding="utf-8")
    )
    return payload["data"]


def report(label, select, score, field="detailed"):
    rows = golden()
    arch_hits = sum(1 for r in rows if select(BUCKET, r["values"]) == r["player_type"])
    val_hits = 0
    worst = (0.0, None)
    for row in rows:
        got = score(BUCKET, row["player_type"], row["values"])
        delta = abs(got - row[field])
        if delta < 1e-4:
            val_hits += 1
        if delta > worst[0]:
            worst = (delta, row["sample"])
    print(
        f"{label:<40} archetype {arch_hits:>3}/256   detailed {val_hits:>3}/256"
        f"   worst delta {worst[0]:.6f} (sample {worst[1]})"
    )
    return arch_hits, val_hits


# --- candidate pre-lerp scoring kernels -------------------------------------


def _scales(values):
    return [
        tables.scale_for(attr, v) for attr, v in zip(reference.tuning_order(), values)
    ]


def _pg_pricing():
    table = tuning.load()
    key = "PerPosition[POINT_GUARD].MultiplierToRelativeAttributeImportanceForPricing"
    return [
        float(table.get(f"{key}[{attr}]", 1.0)) for attr in reference.tuning_order()
    ]


def _price_cap_multipliers(values):
    """AttributePriceCapOverMaxRatioToMultiplierLerp read as 3 (ratio, mult) points."""
    table = tuning.load()
    raw = [
        float(table[f"AttributePriceCapOverMaxRatioToMultiplierLerp[{i}]"])
        for i in range(6)
    ]
    points = [(raw[0], raw[3]), (raw[1], raw[4]), (raw[2], raw[5])]
    caps = body.ceilings(75, 198, 78)
    ceiling = [caps[name] for name in reference.attribute_names()]
    out = []
    for value, cap in zip(values, ceiling):
        ratio = value / cap
        if ratio <= points[0][0]:
            out.append(points[0][1])
        elif ratio >= points[-1][0]:
            out.append(points[-1][1])
        else:
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                if x0 <= ratio <= x1:
                    out.append(y0 + (ratio - x0) / (x1 - x0) * (y1 - y0))
                    break
    return out


def plain(bucket, player_type, values):
    """Baseline: plain weighted sum over a nominal 100."""
    w = tables.weights(bucket, player_type)
    return tables.lerp(bucket, sum(a * b for a, b in zip(w, values)) / 100.0)


def scaled_over_100(bucket, player_type, values):
    """Rating scale applied, denominator held at 100."""
    w = tables.weights(bucket, player_type)
    s = _scales(values)
    return tables.lerp(bucket, sum(a * b * c for a, b, c in zip(w, values, s)) / 100.0)


def plain_renorm(bucket, player_type, values):
    """No rating scale, but renormalised by the actual weight sum."""
    w = tables.weights(bucket, player_type)
    return tables.lerp(bucket, sum(a * b for a, b in zip(w, values)) / sum(w))


def pricing_no_scale(bucket, player_type, values):
    """PerPosition pricing multiplier folded into the weight, no rating scale."""
    w = tables.weights(bucket, player_type)
    p = _pg_pricing()
    num = sum(a * b * c for a, b, c in zip(w, p, values))
    den = sum(a * b for a, b in zip(w, p))
    return tables.lerp(bucket, num / den)


def pricing_scaled(bucket, player_type, values):
    """PerPosition pricing multiplier folded in on top of the rating scale."""
    w = tables.weights(bucket, player_type)
    s = _scales(values)
    p = _pg_pricing()
    num = sum(a * b * c * d for a, b, c, d in zip(w, s, p, values))
    den = sum(a * b * c for a, b, c in zip(w, s, p))
    return tables.lerp(bucket, num / den)


def price_cap_scaled(bucket, player_type, values):
    """Rating-over-ceiling price-cap multiplier folded in on top of the rating scale."""
    w = tables.weights(bucket, player_type)
    s = _scales(values)
    m = _price_cap_multipliers(values)
    num = sum(a * b * c * d for a, b, c, d in zip(w, s, m, values))
    den = sum(a * b * c for a, b, c in zip(w, s, m))
    return tables.lerp(bucket, num / den)


def scale_floor(floor):
    """Rating scale applied only at or above `floor`, otherwise 1.0."""
    scale = tables.rating_scale()

    def kernel(bucket, player_type, values):
        w = tables.weights(bucket, player_type)
        s = [
            scale.get((attr, v), 1.0) if v >= floor else 1.0
            for attr, v in zip(reference.tuning_order(), values)
        ]
        num = sum(a * b * c for a, b, c in zip(w, s, values))
        den = sum(a * b for a, b in zip(w, s))
        return tables.lerp(bucket, num / den)

    return kernel


def scaled_renorm(bucket, player_type, values):
    """The winner: sum(w*s*v) / sum(w*s), then the height lerp. Uncapped."""
    w = tables.weights(bucket, player_type)
    s = _scales(values)
    num = sum(a * b * c for a, b, c in zip(w, s, values))
    den = sum(a * b for a, b in zip(w, s))
    return tables.lerp(bucket, num / den)


def argmax(score):
    def select(bucket, values):
        return max(tables.player_types(), key=lambda pt: score(bucket, pt, values))

    return select


# --- the shipped implementation ---------------------------------------------


def uncapped(bucket, player_type, values):
    """Post-lerp overall for one archetype, before the display cap."""
    return tables.lerp(bucket, archetypes.scaled_score(bucket, player_type, values))


def shipped_score(bucket, player_type, values):
    """The shipped kernel, still scored against the declared archetype."""
    return min(uncapped(bucket, player_type, values), ovr._cap_for(values))


def shipped_select(bucket, values):
    return archetypes.select(bucket, values)


def check_shipped():
    """Cross-check buildlab.ovr against every golden file, including `overall`."""
    rows = golden()
    height = 75
    ints = sum(1 for r in rows if ovr.overall(height, r["values"]) == r["overall"])
    unc = sum(
        1
        for r in rows
        if abs(uncapped(BUCKET, r["uncapped_player_type"], r["values"]) - r["uncapped"])
        < 1e-4
    )
    print(f"{'  mixed_vectors uncapped':<40} {unc:>3}/256")
    print(f"{'  mixed_vectors overall (integer)':<40} {ints:>3}/256")

    urows = uniform()
    ud = sum(
        1
        for r in urows
        if abs(ovr.detailed(height, [r["rating"]] * 21) - r["detailed"]) < 1e-4
    )
    uo = sum(
        1 for r in urows if ovr.overall(height, [r["rating"]] * 21) == r["overall"]
    )
    print(f"{'  uniform_ratings detailed':<40} {ud:>3}/75")
    print(f"{'  uniform_ratings overall (integer)':<40} {uo:>3}/75")

    floor_ok = all(math.floor(r["detailed"]) == r["overall"] for r in rows)
    print(f"{'  overall == floor(detailed)':<40} {floor_ok}")


def main():
    print("ladder (each line scores with the archetype the golden row declares):")
    report("plain weighted sum / 100", argmax(plain), plain)
    report("rating-scaled / 100", argmax(scaled_over_100), scaled_over_100)
    report("plain, renormalised by sum(w)", argmax(plain_renorm), plain_renorm)
    report(
        "PG pricing mult, no rating scale",
        argmax(pricing_no_scale),
        pricing_no_scale,
    )
    report("PG pricing mult + scale, renorm", argmax(pricing_scaled), pricing_scaled)
    report("price-cap mult + scale, renorm", argmax(price_cap_scaled), price_cap_scaled)
    for floor in (80, 85):
        kernel = scale_floor(floor)
        report(f"rating-scale floor {floor}, renorm", argmax(kernel), kernel)
    print()
    print("result:")
    report("rating-scaled, renormalised", argmax(scaled_renorm), scaled_renorm)
    report("  + display clamp (shipped)", shipped_select, shipped_score)
    print()
    print("buildlab.ovr cross-checks:")
    check_shipped()


if __name__ == "__main__":
    main()
