"""Extract POIs from a complete Geofabrik Cyprus PBF."""
from __future__ import annotations
from collections import Counter
from typing import Any
import osmium
from shapely.geometry import LineString, MultiPolygon, Polygon
from cy_poi.categories import category

def _record(kind: str, osm_id: int, tags: dict[str, str], lat: float, lon: float,
            version: int | None, timestamp: str | None) -> dict[str, Any] | None:
    cat = category(tags)
    if cat is None: return None
    if kind not in {"node", "way", "relation"} or osm_id <= 0 or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("invalid OSM identity or coordinate")
    name = next((tags[k].strip() for k in ("name", "name:en", "brand", "operator") if tags.get(k, "").strip()), "")
    def first(*keys: str) -> str: return next((tags[k].strip() for k in keys if tags.get(k, "").strip()), "")
    address = first("addr:full")
    if not address:
        street, number = first("addr:street", "addr:place"), first("addr:housenumber")
        primary = " ".join(v for v in (number, street) if v)
        locality = " ".join(v for v in (first("addr:suburb", "addr:city"), first("addr:postcode")) if v)
        address = ", ".join(v for v in (primary, locality) if v)
    row = {"osmType": kind, "osmId": int(osm_id), "osmVersion": version,
           "osmTimestamp": timestamp, "name": name[:4096], "category": cat,
           "lat": float(lat), "lon": float(lon), "address": address[:4096],
           "phone": first("contact:phone", "phone", "contact:mobile", "mobile")[:4096],
           "website": first("contact:website", "website", "contact:url", "url")[:4096],
           "openingHours": first("opening_hours")[:4096], "wheelchair": first("wheelchair")[:4096],
           "cuisine": first("cuisine")[:4096], "religion": first("religion")[:4096], "sport": first("sport")[:4096]}
    if any("\x00" in str(v) for v in row.values()): raise ValueError("NUL in text")
    return row

class CyprusHandler(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__(); self.records: dict[tuple[str, int], dict[str, Any]] = {}; self.skipped = Counter()
        self.relation_candidates: dict[int, dict[str, str]] = {}; self.relation_areas: set[int] = set()
    def _add(self, obj: Any, kind: str, lat: float, lon: float) -> None:
        try:
            tags = {tag.k: tag.v for tag in obj.tags}
            row = _record(kind, obj.id, tags, lat, lon, getattr(obj, "version", None),
                          obj.timestamp.isoformat() if getattr(obj, "timestamp", None) else None)
            if row is None: return
            key = (kind, int(obj.id))
            if key in self.records: self.skipped["duplicate_identity"] += 1
            self.records[key] = row
        except (ValueError, OverflowError): self.skipped["invalid_record"] += 1
    def node(self, node: Any) -> None:
        tags = {tag.k: tag.v for tag in node.tags}
        if category(tags) is None: return
        location = node.location
        if location.valid(): self._add(node, "node", location.lat, location.lon)
        else: self.skipped["node_missing_location"] += 1
    def way(self, way: Any) -> None:
        tags = {tag.k: tag.v for tag in way.tags}
        if category(tags) is None: return
        try:
            coords = [(n.lon, n.lat) for n in way.nodes if n.location.valid()]
            if len(coords) < 2: raise ValueError("incomplete geometry")
            geom = Polygon(coords) if len(coords) >= 4 and coords[0] == coords[-1] else LineString(coords)
            if geom.is_empty or not geom.is_valid: raise ValueError("invalid geometry")
            point = geom.representative_point() if geom.geom_type == "Polygon" else geom.interpolate(0.5, normalized=True)
            self._add(way, "way", point.y, point.x)
        except (ValueError, OverflowError): self.skipped["way_invalid_geometry"] += 1
    def relation(self, relation: Any) -> None:
        tags = {tag.k: tag.v for tag in relation.tags}
        if category(tags) is not None: self.relation_candidates[int(relation.id)] = tags

    def area(self, area: Any) -> None:
        if area.from_way(): return
        relation_id = int(area.orig_id())
        tags = self.relation_candidates.get(relation_id, {tag.k: tag.v for tag in area.tags})
        if category(tags) is None: return
        try:
            polygons = []
            for outer in area.outer_rings():
                shell = [(node.lon, node.lat) for node in outer if node.location.valid()]
                holes = [[(node.lon, node.lat) for node in inner if node.location.valid()]
                         for inner in area.inner_rings(outer)]
                if len(shell) < 4: continue
                polygon = Polygon(shell, holes)
                if polygon.is_valid and not polygon.is_empty: polygons.append(polygon)
            if not polygons: raise ValueError("relation has no valid polygon rings")
            geometry = MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]
            point = geometry.representative_point()
            timestamp = area.timestamp.isoformat() if area.timestamp else None
            row = _record("relation", relation_id, tags, point.y, point.x, area.version, timestamp)
            if row is not None: self.records[("relation", relation_id)] = row
            self.relation_areas.add(relation_id)
        except (ValueError, OverflowError): self.skipped["relation_invalid_geometry"] += 1

def extract(pbf_path: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    handler = CyprusHandler()
    index_path = str(pbf_path) + ".node-index"
    candidate_tags = [
        ("amenity", value) for value in ("shelter", "hospital", "clinic", "doctors", "pharmacy", "police", "fire_station", "drinking_water", "fuel", "toilets", "school", "place_of_worship", "atm", "bank", "parking", "charging_station", "restaurant", "fast_food", "cafe", "bus_station", "ferry_terminal", "post_office", "food_court")
    ] + [("healthcare", value) for value in ("hospital", "clinic", "doctor", "pharmacy")]
    candidate_tags += [("social_facility", "shelter"), ("emergency:social_facility", "shelter"),
                       ("natural", "spring"), ("man_made", "water_well"),
                       ("public_transport", "station"), ("public_transport", "platform"),
                       ("highway", "bus_stop")]
    candidate_tags += [("leisure", value) for value in ("stadium", "sports_centre", "pitch")]
    candidate_tags += [("shop", value) for value in ("supermarket", "convenience", "greengrocer", "bakery")]
    tag_filter = osmium.filter.TagFilter(*candidate_tags)
    processor = (osmium.FileProcessor(pbf_path)
                 .with_locations(f"sparse_file_array,{index_path}")
                 .with_areas(tag_filter)
                 .with_filter(osmium.filter.TagFilter(*candidate_tags)))
    for obj in processor:
        if obj.is_area():
            handler.area(obj)
        elif obj.is_node():
            handler.node(obj)
        elif obj.is_way():
            handler.way(obj)
        elif obj.is_relation():
            handler.relation(obj)
    handler.skipped["poi_relation_geometry_unsupported"] = len(set(handler.relation_candidates) - handler.relation_areas)
    return sorted(handler.records.values(), key=lambda row: (row["osmType"], row["osmId"])), dict(handler.skipped)
