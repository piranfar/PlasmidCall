#!/usr/bin/env python3
"""P1.11-CORRECTED-TRUTH-ALL79: deterministic replicon-accession resolution.

Frozen rule. Selection NEVER consults truth counts, model output or resulting class balance.

  1  accession strings are normalised by stripping surrounding whitespace only; VERSIONS ARE
     PRESERVED verbatim (AP040898.1 stays AP040898.1)
  2  the accession must be present in the downloaded reference FASTA deflines
  3  RefSeq-Accn is used when it is non-'na' AND present in the FASTA
  4  otherwise GenBank-Accn when it is non-'na' AND present in the FASTA
  5  if both columns are populated they must map to the same assembly-report row; two rows
     claiming one FASTA accession is a conflict
  6  otherwise fail closed: no role is assigned and the reason is recorded
"""
NA = ("na", "")


def norm(a):
    return (a or "").strip()


def resolve_row(refseq_accn, genbank_accn, fasta_names):
    """-> (key or None, source_label)"""
    rs, gb = norm(refseq_accn), norm(genbank_accn)
    rs_ok = rs.lower() not in NA and rs in fasta_names
    gb_ok = gb.lower() not in NA and gb in fasta_names
    if rs_ok:
        return rs, "RefSeq-Accn"
    if gb_ok:
        return gb, "GenBank-Accn"
    return None, "no_accession_matches_reference_FASTA"


def resolve_report(rows, fasta_names):
    """rows: iterable of assembly-report field lists. Returns (role_keys, diagnostics)."""
    role, resolved, unresolved, conflict, blocked = {}, [], [], [], set()
    for p in rows:
        if len(p) < 9:
            continue
        key, src = resolve_row(p[6], p[4], fasta_names)
        if key is None:
            unresolved.append({"sequence_name": p[0], "refseq_accn": norm(p[6]),
                               "genbank_accn": norm(p[4]), "reason": src})
        elif key in blocked:
            continue
        elif key in role:
            conflict.append({"accession": key, "sequence_name": p[0],
                             "reason": "duplicate assembly-report rows map to one FASTA accession"})
            role.pop(key, None)
            blocked.add(key)
        else:
            role[key] = {"class": p[3].lower(), "molecule": p[2], "length": int(p[8]),
                         "genbank": p[4], "refseq": p[6], "accession_source": src}
            resolved.append({"accession": key, "source": src, "class": p[3].lower()})
    return role, {"n_resolved": len(resolved), "resolved": resolved,
                  "unresolved": unresolved, "conflicts": conflict,
                  "by_source": {"RefSeq-Accn": sum(1 for x in resolved
                                                   if x["source"] == "RefSeq-Accn"),
                                "GenBank-Accn": sum(1 for x in resolved
                                                    if x["source"] == "GenBank-Accn")},
                  "selection_used_truth_counts_or_model_output": False}
