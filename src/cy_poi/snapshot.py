"""Deterministic SQLite snapshot and authenticated manifest primitives."""
from __future__ import annotations
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

SCHEMA_VERSION = 1
SCHEMA = """
PRAGMA application_id=1129336905;
PRAGMA user_version=1;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE pois (
  osm_type TEXT NOT NULL CHECK(osm_type IN ('node','way','relation')),
  osm_id INTEGER NOT NULL CHECK(osm_id > 0), osm_version INTEGER, osm_timestamp TEXT,
  name TEXT NOT NULL, category TEXT NOT NULL, latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
  longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180), address TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '', opening_hours TEXT NOT NULL DEFAULT '',
  wheelchair TEXT NOT NULL DEFAULT '', cuisine TEXT NOT NULL DEFAULT '', religion TEXT NOT NULL DEFAULT '', sport TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(osm_type, osm_id)
);
CREATE INDEX poi_location ON pois(latitude, longitude);
CREATE INDEX poi_name ON pois(name COLLATE NOCASE);
CREATE INDEX poi_category ON pois(category);
"""

def write_snapshot(path: Path, records: Iterable[dict[str, Any]], metadata: dict[str, str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): path.unlink()
    rows = sorted(records, key=lambda r: (r["osmType"], int(r["osmId"])))
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO metadata(key,value) VALUES(?,?)", sorted(metadata.items()))
        db.executemany("""INSERT INTO pois VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            (r["osmType"], r["osmId"], r.get("osmVersion"), r.get("osmTimestamp"), r["name"], r["category"],
             r["lat"], r["lon"], r.get("address", ""), r.get("phone", ""), r.get("website", ""),
             r.get("openingHours", ""), r.get("wheelchair", ""), r.get("cuisine", ""), r.get("religion", ""), r.get("sport", "")) for r in rows))
        db.commit()
        check = db.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok": raise ValueError(f"SQLite integrity check failed: {check}")
        if db.execute("SELECT COUNT(*) FROM pois").fetchone()[0] != len(rows): raise ValueError("POI record count mismatch")
    return len(rows)

def gzip_snapshot(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, target.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as dst:
            while chunk := src.read(1024 * 1024): dst.write(chunk)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()

def manifest(version: str, extract_timestamp: str, artifact_url: str, archive: Path,
             count: int, boundary_sha256: str, source_timestamp: str | None,
             source_extract_sha256: str) -> dict[str, Any]:
    parsed = urlparse(artifact_url)
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password or
            not parsed.path.startswith("/kkraso01/cy_poi/releases/download/") or parsed.query or parsed.fragment):
        raise ValueError("artifact URL must be a cy_poi GitHub Release URL")
    return {
      "schemaVersion": 1, "region": "CY", "sourceId": "osm-cyprus-poi-snapshot-v1",
      "completeSnapshot": True, "sourceVersion": version, "sequenceNumber": int(version.replace("-", "").replace(".", "")),
      "sourceTimestamp": source_timestamp, "recordCount": count, "boundarySha256": boundary_sha256,
      "source": {"name": "OpenStreetMap / Geofabrik", "extractTimestamp": extract_timestamp,
                 "extractSha256": source_extract_sha256,
                 "url": "https://download.geofabrik.de/europe/cyprus-latest.osm.pbf"},
      "artifactUrl": artifact_url, "artifactSizeBytes": archive.stat().st_size,
      "artifactSha256": sha256(archive), "artifactFormat": "sqlite-gzip-v1"
    }

def canonical_json(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
