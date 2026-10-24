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
