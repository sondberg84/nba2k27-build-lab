"""Copy the user's own source documents into data/local and record hashes.

These are not downloaded from an upstream repository — they are files the user
maintains. They get the same manifest and hash treatment as vendored data so
the engine can detect when one changes underneath it.
"""

import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT.parent
DEST = ROOT / "data" / "local"

FILES = {
    "local/animation_requirements.md": "2k27-animation-requirements.md",
}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "data" / "SOURCES.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    entries = {}
    for rel, filename in FILES.items():
        origin = SOURCE_DIR / filename
        if not origin.exists():
            raise SystemExit(f"missing source file {origin}")
        payload = origin.read_bytes()
        out = DEST / pathlib.PurePosixPath(rel).name
        out.write_bytes(payload)
        entries[rel] = {
            "local": f"data/local/{out.name}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        print(f"{rel}  {len(payload)} bytes")

    manifest["sources"] = [
        s for s in manifest["sources"] if s.get("name") != "user-local-documents"
    ]
    manifest["sources"].append(
        {
            "name": "user-local-documents",
            "url": "local",
            "commit": "n/a",
            "files": entries,
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"recorded {len(entries)} local files in the manifest")


if __name__ == "__main__":
    main()
