#!/usr/bin/env python3
"""List tagged POI relations for geometry policy review (no network access)."""
import json
from pathlib import Path
import sys
import osmium

from cy_poi.categories import category

path = Path(sys.argv[1])
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
tags = [("amenity", v) for v in ("shelter", "hospital", "clinic", "doctors", "pharmacy", "police", "fire_station", "drinking_water", "fuel", "toilets", "school", "place_of_worship", "atm", "bank", "parking", "charging_station", "restaurant", "fast_food", "cafe", "bus_station", "ferry_terminal", "post_office", "food_court")]
tags += [("healthcare", v) for v in ("hospital", "clinic", "doctor", "pharmacy")]
tags += [("social_facility", "shelter"), ("emergency:social_facility", "shelter"), ("natural", "spring"), ("man_made", "water_well"), ("public_transport", "station"), ("public_transport", "platform"), ("highway", "bus_stop")]
tags += [("leisure", v) for v in ("stadium", "sports_centre", "pitch")]
tags += [("shop", v) for v in ("supermarket", "convenience", "greengrocer", "bakery")]
for obj in osmium.FileProcessor(path).with_filter(osmium.filter.TagFilter(*tags)):
    if obj.is_relation():
        d = {t.k:t.v for t in obj.tags}
        cat = category(d)
        if cat: print(json.dumps({"id":obj.id,"category":cat,"tags":d,"members":[{"type":m.type,"ref":m.ref,"role":m.role} for m in obj.members]},ensure_ascii=False))
