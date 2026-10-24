#!/usr/bin/env python3
"""Build one Cyprus POI snapshot and its release manifest from a Geofabrik PBF."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse
import urllib.request
from urllib.error import HTTPError, URLError

from cy_poi.extract import extract
from cy_poi.snapshot import canonical_json, gzip_snapshot, manifest, sha256, write_snapshot

PBF_URL = "https://download.geofabrik.de/europe/cyprus-latest.osm.pbf"
MAX_PBF_BYTES = 1_073_741_824
BOUNDARY_HASH = "47c5f9ae82a8d001d80a67d082b4b7ce3e016c6feae3664299297ea28bdc9b4c"

def source_timestamp_from_filename(filename: str) -> str | None:
    match = re.search(r"cyprus-(\d{6}|\d{8})\.osm\.pbf$", filename)
    if not match: return None
    raw = match.group(1)
    fmt = "%y%m%d" if len(raw) == 6 else "%Y%m%d"
    try: return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError: return None

def download(url: str, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "cy_poi snapshot builder"})
    partial = destination.with_suffix(destination.suffix + ".partial")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
                final_url = response.geturl()
                final = urlparse(final_url)
                if final.scheme != "https" or final.hostname != "download.geofabrik.de":
                    raise RuntimeError("Geofabrik redirected outside its official download host")
                expected = response.headers.get("Content-Length")
                if expected is not None and int(expected) > MAX_PBF_BYTES:
                    raise RuntimeError("Geofabrik Cyprus PBF exceeded the configured size limit")
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_PBF_BYTES: raise RuntimeError("Geofabrik Cyprus PBF exceeded the configured size limit")
                    out.write(chunk)
                out.flush()
                if size == 0 or (expected is not None and size != int(expected)):
                    raise IOError("Geofabrik PBF transfer was empty or incomplete")
            partial.replace(destination)
            return final_url
        except RuntimeError:
            partial.unlink(missing_ok=True)
            raise
        except (HTTPError, URLError, TimeoutError, OSError):
            partial.unlink(missing_ok=True)
            if attempt == 2: raise
            time.sleep(2 ** attempt)
    raise AssertionError("bounded download retries exhausted")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True, help="monotonic version such as 20261024.1")
    parser.add_argument("--artifact-url", required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    pbf = args.pbf or out / "cyprus.osm.pbf"
    downloaded_url = download(PBF_URL, pbf) if not args.pbf else None
    if downloaded_url:
        dated = Path(downloaded_url.split("?")[0]).name
        if re.fullmatch(r"cyprus-\d{6,8}\.osm\.pbf", dated):
            dated_path = out / dated
            pbf.replace(dated_path)
            pbf = dated_path
    if not pbf.is_file() or pbf.stat().st_size == 0 or pbf.stat().st_size > MAX_PBF_BYTES:
        raise RuntimeError("The Cyprus PBF is missing, empty or exceeds the configured size limit")
    rows, skipped = extract(str(pbf))
    if not rows: raise RuntimeError("Extraction produced an empty POI snapshot; refusing release")
    incomplete = {reason: count for reason, count in skipped.items() if count}
    if incomplete:
        raise RuntimeError(f"Extraction is incomplete; refusing complete snapshot: {incomplete}")
    # Geofabrik's regional filenames carry the actual source snapshot date.
    source_timestamp = source_timestamp_from_filename(pbf.name)
    extract_timestamp = source_timestamp or ""
    name = f"cyprus-poi-{args.version.replace('.', '-')}.sqlite"
    database, archive = out / name, out / f"{name}.gz"
    metadata = {"schema_version": "1", "region": "CY", "source": "OpenStreetMap / Geofabrik",
                "source_url": PBF_URL, "source_timestamp": source_timestamp or "",
                "source_version": args.version, "complete_snapshot": "true",
                "extraction_rules": "1", "record_count": str(len(rows))}
    write_snapshot(database, rows, metadata); gzip_snapshot(database, archive)
    value = manifest(args.version, extract_timestamp, args.artifact_url, archive, len(rows),
                     BOUNDARY_HASH, source_timestamp, sha256(pbf))
    (out / "manifest.json").write_bytes(canonical_json(value))
    report = {"source": str(pbf), "sourceBytes": pbf.stat().st_size, "recordCount": len(rows),
              "skipped": skipped, "snapshot": str(database), "snapshotBytes": database.stat().st_size,
              "archive": str(archive), "archiveBytes": archive.stat().st_size, "manifest": value}
    (out / "validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
