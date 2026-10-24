"""Ed25519 detached manifest signing; the private key is accepted only from CI secrets."""
from __future__ import annotations
import base64
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cy_poi.snapshot import canonical_json

def sign(manifest: dict, private_key_b64: str, expected_public_key: Path) -> bytes:
    if not private_key_b64.strip(): raise ValueError("CY_POI_ED25519_PRIVATE_KEY_B64 is required")
    raw = base64.b64decode(private_key_b64, validate=True)
    key = Ed25519PrivateKey.from_private_bytes(raw)
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pinned = serialization.load_pem_public_key(expected_public_key.read_bytes())
    pinned_raw = pinned.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if public != pinned_raw: raise ValueError("CI signing key does not match the committed public verification key")
    return key.sign(canonical_json(manifest))
