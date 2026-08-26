"""Download upstream dataset files at a pinned commit and write the manifest."""

import hashlib
import json
import pathlib
import urllib.request

REPO = "lightmatmul/nba2k27-builder-dataset"
COMMIT = "957d0095182702e34f671e81ecb81efa9def9cb3"
FILES = [
    "reference/attributes.json",
    "reference/enums.json",
    "bodies/legal_bodies.json",
    "bodies/attribute_caps_sample.json",
    "overall/mixed_vectors.json",
    "overall/uniform_ratings.json",
    "overall/official_ui_verified.json",
    "badges/definitions.json",
    "badges/tier_requirements.json",
    "badges/token_costs.json",
    "badges/token_contributions.json",
    "cap_breakers/gains_by_rating.json",
    "tuning/progression_attributes.txt",
]

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "engine"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    entries = {}
    for rel in FILES:
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{rel}"
        with urllib.request.urlopen(url) as response:
            payload = response.read()
        out = DEST / rel.replace("/", "__")
        out.write_bytes(payload)
        entries[rel] = {
            "local": f"data/engine/{out.name}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        print(f"{rel}  {len(payload)} bytes")

    manifest = {
        "sources": [
            {
                "name": "nba2k27-builder-dataset",
                "url": f"https://github.com/{REPO}",
                "commit": COMMIT,
                "files": entries,
            }
        ]
    }
    (ROOT / "data" / "SOURCES.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote manifest with {len(entries)} files")


if __name__ == "__main__":
    main()
