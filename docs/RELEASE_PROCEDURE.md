# Snapshot release procedure

1. Maintain and protect `main`; review extraction/schema changes through pull requests.
2. Provision a dedicated Ed25519 key outside the repository. Commit its PEM public key as `keys/update-public-key.pem` and place only base64 raw private bytes in the protected Actions secret `CY_POI_ED25519_PRIVATE_KEY_B64`.
3. Dispatch `Build and publish Cyprus snapshot` or wait for its weekly run.
4. The job downloads the official regional PBF, builds and validates the SQLite archive, refuses empty output and unsupported tagged POI relations, generates SHA-256 metadata, and signs canonical manifest JSON.
5. It creates a versioned immutable GitHub Release asset, verifies the public asset URL, then updates the manifest and detached signature on `main` last.
6. Validate the raw manifest, signature, release asset size and SHA-256 using an independent client before enabling Android update application.

The repository currently has no trust key, so the publishing workflow intentionally fails closed until key custody and Android pinning are configured. ODbL/legal review is also required before distributing the generated database.
