# Cyprus POI update provider

This independent repository builds complete Cyprus place snapshots from the official [Geofabrik Cyprus OpenStreetMap extract](https://download.geofabrik.de/europe/cyprus.html). It produces a versioned SQLite database and gzip archive, validates SQLite integrity and record counts, and emits a manifest with the real artifact size and SHA-256. Raw PBFs and generated packages are build artifacts and must never be committed.

## Build locally

Use Python 3.11–3.13. Install the pinned project dependencies and run `pytest`. To build, place the dated Cyprus PBF on a data volume and run:

```sh
python scripts/build_snapshot.py --pbf /data/cyprus-YYYYMMDD.osm.pbf --output-dir /data/cy-poi-output --version YYYYMMDD.1 --artifact-url https://github.com/kkraso01/cy_poi/releases/download/vYYYYMMDD.1/cyprus-poi-YYYYMMDD-1.sqlite.gz
```

If `--pbf` is omitted, the script downloads only the Cyprus regional extract and follows redirects only within Geofabrik's HTTPS download host. Never substitute an Overpass query or a different regional extract.

The extraction reuses SurvivalAI's current POI category identifiers and data fields. Nodes use their coordinates. Ways use an interior representative point for closed polygons and a midpoint for linear geometries. PyOsmium assembles multipolygon/boundary relation areas from their member ways. Invalid or incomplete tagged geometry is counted and blocks release publication so the provider cannot label an incomplete extract complete.

## Publishing

`.github/workflows/build-snapshot.yml` runs weekly or by manual dispatch. It publishes an immutable GitHub Release asset, then updates `manifest.json` on `main` only after the release asset is reachable. The manifest is signed with Ed25519. Set the repository secret `CY_POI_ED25519_PRIVATE_KEY_B64` to a 32-byte raw Ed25519 private key encoded as base64. Commit only the corresponding public PEM at `keys/update-public-key.pem`; never commit the private key. The workflow compares the private key's public half to the committed verifier and fails closed if signing is unavailable or mismatched. Protect `main` and restrict Actions write permissions.

No signing key is provisioned in this initial source bootstrap. Until one is installed and pinned in SurvivalAI, the manifest must not be consumed for automatic production application.

## Data and license

The source is © OpenStreetMap contributors and is available under the Open Database License (ODbL). Derived database distributions must provide attribution and satisfy ODbL share-alike obligations where applicable. See [`licenses/OSM-ATTRIBUTION.md`](licenses/OSM-ATTRIBUTION.md) and have the repository's legal declaration reviewed before production distribution.

## Package contract

The SQLite schema is version 1 in [`schemas/poi-snapshot-v1.sql`](schemas/poi-snapshot-v1.sql). Canonical identity is `(osm_type, osm_id)` with 64-bit IDs. The separate metadata table records source version, extract timestamp, extraction rules and count. `manifest.json` points at a release asset and records SHA-256, compressed byte count, source timestamp, schema, region and snapshot completeness. A detached `manifest.json.sig` signs canonical UTF-8 JSON bytes. The app must pin the verifier and allow only this repository's raw manifest and release download locations.
