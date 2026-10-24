#!/usr/bin/env python3
import json
import os
from pathlib import Path
from cy_poi.signing import sign

manifest_path = Path(os.environ.get("CY_POI_MANIFEST", "artifacts/manifest.json"))
signature = sign(json.loads(manifest_path.read_text(encoding="utf-8")),
                 os.environ.get("CY_POI_ED25519_PRIVATE_KEY_B64", ""),
                 Path("keys/update-public-key.pem"))
manifest_path.with_suffix(manifest_path.suffix + ".sig").write_bytes(signature)
