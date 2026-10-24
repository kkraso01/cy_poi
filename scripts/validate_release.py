#!/usr/bin/env python3
"""Independent package/manifest/SQLite validation before signing or publication."""
import argparse
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--archive", type=Path, required=True)
parser.add_argument("--manifest", type=Path, required=True)
args = parser.parse_args()
manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
compressed = args.archive.read_bytes()
assert len(compressed) == manifest["artifactSizeBytes"], "compressed byte count mismatch"
assert hashlib.sha256(compressed).hexdigest() == manifest["artifactSha256"], "artifact SHA-256 mismatch"
database = args.archive.with_suffix("")
database.write_bytes(gzip.decompress(compressed))
db = sqlite3.connect(database)
try:
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    count = db.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
    categories = dict(db.execute("SELECT category, COUNT(*) FROM pois GROUP BY category"))
    version = db.execute("SELECT value FROM metadata WHERE key='source_version'").fetchone()[0]
    assert integrity == "ok", f"SQLite integrity check failed: {integrity}"
    assert count == manifest["recordCount"], "record count mismatch"
    assert version == manifest["sourceVersion"], "source version mismatch"
    assert len(categories) > 0, "snapshot has no POI categories"
    print(json.dumps({"integrity": integrity, "recordCount": count, "categories": categories,
                      "sourceVersion": version, "compressedBytes": len(compressed),
                      "uncompressedBytes": database.stat().st_size,
                      "sha256": manifest["artifactSha256"]}, ensure_ascii=False, sort_keys=True))
finally:
    db.close()
    database.unlink(missing_ok=True)
