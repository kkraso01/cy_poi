# Data sources and provenance

The sole input is the complete regional Cyprus PBF from <https://download.geofabrik.de/europe/cyprus-latest.osm.pbf>. Its redirected dated filename supplies the source date when available. The extractor does not query Overpass, does not combine third-party datasets, and does not clip the extract to a politically selected part of Cyprus.

The current rules map OSM tags to SurvivalAI category identifiers. Node coordinates are used directly. Closed ways with valid polygon geometry use an interior representative point; linear ways use their midpoint by length. Multipolygon and boundary POI relations are assembled from member ways with PyOsmium. Invalid or incomplete tagged geometries are counted and block publication. The provider records source object versions/timestamps where present and never fabricates missing metadata.

Data attribution and license guidance is in [`../licenses/OSM-ATTRIBUTION.md`](../licenses/OSM-ATTRIBUTION.md).
