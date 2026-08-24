# Security policy

## Reporting

Report suspected vulnerabilities or accidental disclosure privately to the repository owner. Do
not open a public issue for a suspected credential exposure.

## What this repository does not contain

No credentials, private keys, API tokens, cloud identifiers (OCIDs), server addresses, patient
identifiers or restricted metadata are stored here. This is enforced by a scan run as part of the
release-readiness checks (`scripts/release/release_check.py`), which fails the build on any hit.

## Handling of research data

* Raw sequencing reads are **public ENA data** and are not redistributed. They are referenced by
  run accession with per-file MD5s.
* No human-subject or patient-derived data is used anywhere in this project.
* Derived artefacts (assemblies, prediction tables, receipts) contain no personal data.

## Known incident

On 2026-08-23 an SSH private key for the compute host was read into an assistant conversation
transcript by a file-mention. The key material was never written to this repository and never
will be. **Status: not yet rotated at the time of writing** — the owner is required to rotate the
key pair, and this note stays until rotation is confirmed. No repository content was exposed by
the incident.
