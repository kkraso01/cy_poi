import gzip
import sqlite3
from pathlib import Path
import shutil

import pytest

from cy_poi.categories import category
from cy_poi.extract import _record, extract
from cy_poi.snapshot import gzip_snapshot, manifest, write_snapshot
from scripts.build_snapshot import source_timestamp_from_filename

def test_android_category_mapping_is_preserved():
    assert category({"amenity": "drinking_water"}) == "water"
    assert category({"amenity": "pharmacy"}) == "pharmacy"
    assert category({"shop": "supermarket"}) == "supermarket"
    assert category({"amenity": "unknown"}) is None

def test_record_preserves_osm_identity_unicode_and_metadata():
    row = _record("way", 9_223_372_036_854_000, {"amenity":"cafe", "name":"Καφενείο Şehir", "phone":"123"}, 35.1, 33.2, 4, "2026-10-20T00:00:00Z")
    assert row and row["osmType"] == "way" and row["osmId"] == 9_223_372_036_854_000
    assert row["name"] == "Καφενείο Şehir" and row["phone"] == "123"

def test_invalid_identity_and_coordinate_rejected():
    with pytest.raises(ValueError): _record("node", 0, {"amenity":"cafe"}, 0, 0, None, None)
    with pytest.raises(ValueError): _record("node", 1, {"amenity":"cafe"}, 91, 0, None, None)

def test_geofabrik_six_digit_date_is_parsed_as_source_date():
    assert source_timestamp_from_filename("cyprus-261023.osm.pbf") == "2026-10-23T00:00:00Z"
    assert source_timestamp_from_filename("cyprus-latest.osm.pbf") is None

def test_fixture_extracts_node_way_polygon_and_multipolygon_relation(tmp_path: Path):
    fixture = Path(__file__).parent / "fixtures" / "mini-cyprus.osm"
    local_fixture = tmp_path / fixture.name
    shutil.copyfile(fixture, local_fixture)
    rows, skipped = extract(str(local_fixture))
    by_key = {(row["osmType"], row["osmId"]): row for row in rows}
    assert by_key[("node", 9)]["category"] == "water"
    assert by_key[("way", 10)]["category"] == "cafe"
    assert 33.0 < by_key[("way", 10)]["lon"] < 33.002
    assert by_key[("relation", 100)]["category"] == "school"
    assert 33.010 < by_key[("relation", 100)]["lon"] < 33.012
    assert skipped["poi_relation_geometry_unsupported"] == 0

def test_snapshot_integrity_schema_and_archive_round_trip(tmp_path: Path):
    row = _record("node", 4, {"amenity":"drinking_water", "name":"Water point"}, 35, 33, None, None)
    db_path, gz_path = tmp_path / "snapshot.sqlite", tmp_path / "snapshot.sqlite.gz"
    assert write_snapshot(db_path, [row], {"region":"CY", "schema_version":"1"}) == 1
    with sqlite3.connect(db_path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT osm_type,osm_id,category FROM pois").fetchone() == ("node",4,"water")
    gzip_snapshot(db_path, gz_path)
    assert gzip.decompress(gz_path.read_bytes()) == db_path.read_bytes()

def test_manifest_refuses_untrusted_hosts(tmp_path: Path):
    archive = tmp_path / "a.gz"; archive.write_bytes(b"test")
    with pytest.raises(ValueError): manifest("20261024.1", "", "https://example.com/a", archive, 1, "0"*64, None, "0"*64)
    with pytest.raises(ValueError): manifest("20261024.1", "", "https://github.com.evil/kkraso01/cy_poi/releases/download/v/a", archive, 1, "0"*64, None, "0"*64)
