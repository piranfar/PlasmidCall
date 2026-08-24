# P1.11 preservation and verification tooling

The scripts that produced the P1.11 preservation receipts. They are kept so the archives can be
re-verified independently, rather than the receipts being unreproducible assertions.

Nothing here embeds a credential, key path or host. Supply them at run time:

    export P111_SSH_KEY=/path/to/private.key      # never committed, never printed
    export P111_SSH_HOST=user@host
    export P111_WORKDIR=/some/scratch             # defaults to the current directory

## Order of use

| Script | Purpose |
|---|---|
| `scope_raw.sh` | Build the explicit transfer set, size it, and gate on the 100 GB approval threshold before anything moves. |
| `manifest_raw.sh` | Finalise the set and build a relative-path SHA-256 manifest on the source host. |
| `transfer_raw.sh` | Stream the set to the destination in chunks, so a dropped session costs one chunk rather than the whole transfer. Idempotent. |
| `verify_raw_dest.py` | Verify **every** destination file against the source manifest and write `PRESERVATION_RECEIPT.json`. Requires zero absent and zero mismatches. |
| `verify_archives.py` | Verify the manuscript and Docker archives. Does **not** stop at the checksum of the compressed container: it streams the archive open and re-hashes every member against the scientific manifest carried inside it, and checks all 16 OCI image identities via `index.json`. |
| `final_repack.sh` | Regenerate the archive manifest, verify every row by full recomputation, and repack. |
| `fix_audit_repack.sh` | One-off correction retained for provenance (see below). |
| `final_server_audit.py` | Decide whether the compute instance can be stopped. Reports only — it performs no infrastructure action. |

## Two lessons worth keeping

**Sampling is not verification.** The first archive manifest listed its own temporary file
`ARCHIVE_MANIFEST.tsv.new` — the `find` excluded `ARCHIVE_MANIFEST.tsv` but not its temp name, so
the manifest recorded an empty file that the subsequent `mv` removed. A 400-row spot check passed;
full verification caught it. `verify_archives.py` therefore re-hashes every member, never a sample.

**A file cannot record its own container's digest.** The audit inside the archive used to carry
`packaged_sha256`, which no repack can ever make correct. That field was removed rather than
chased; the authoritative digest lives outside, in the `.sha256` sidecar and `FINAL_SERVER_AUDIT.json`.

## Distinguish three actions

`final_server_audit.py` speaks only to **stopping the compute instance with its Block Volume
retained** — reversible, data intact. It never addresses **terminating the instance** or
**deleting/detaching the volume**, and performs none of the three.
