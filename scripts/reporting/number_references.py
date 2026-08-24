# -*- coding: utf-8 -*-
"""Assign reference numbers in strict order of first appearance and render the manuscript.

Nature style requires references numbered sequentially as they appear across text, Methods,
tables and figure legends. This pass is the single source of that numbering: the manuscript
source carries {{key}} markers only, and this script produces the rendered manuscript plus a
reference list in the matching order.

Fails closed on: an unknown citation key, or a reference in the bibliography that is never cited.
"""
import io, re, sys, json, importlib.util

SRC = "docs/manuscript/PLASMIDCALL_MANUSCRIPT_FINAL.md"
REFS_PY = ("<local>/AppData/Local/Temp/claude/"
           "E--Github-Project-amr-evidence-warehouse/"
           "35327ed9-1375-43a0-8af3-3c7d582dd2f9/scratchpad/refs.py")


def load_refs():
    spec = importlib.util.spec_from_file_location("refsmod", REFS_PY)
    m = importlib.util.module_from_spec(spec)
    import os
    cwd = os.getcwd()
    spec.loader.exec_module(m)          # regenerates the bibliography files as a side effect
    os.chdir(cwd)
    return {r["key"]: r for r in m.R}, m


def render(src_text, refs, mod, sup=True):
    """Replace {{key}} runs with superscript numbers in first-appearance order."""
    order, seen = [], {}

    def num(k):
        if k not in seen:
            order.append(k)
            seen[k] = len(order)
        return seen[k]

    # collapse consecutive markers into one citation group
    def group(m):
        keys = re.findall(r"\{\{([a-z0-9_]+)\}\}", m.group(0))
        bad = [k for k in keys if k not in refs]
        if bad:
            raise SystemExit("unknown citation key(s): %s" % bad)
        ns = sorted({num(k) for k in keys})
        # contract runs of three or more into a range
        out, i = [], 0
        while i < len(ns):
            j = i
            while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
                j += 1
            if j - i >= 2:
                out.append("%d\u2013%d" % (ns[i], ns[j]))
            else:
                out.extend(str(n) for n in ns[i:j + 1])
            i = j + 1
        s = ",".join(out)
        return ("^%s^" % s) if sup else ("[%s]" % s)

    text = re.sub(r"(?:\{\{[a-z0-9_]+\}\})+", group, src_text)
    return text, order


def main():
    refs, mod = load_refs()
    src = io.open(SRC, encoding="utf-8").read()
    text, order = render(src, refs, mod)

    uncited = [k for k in refs if k not in order]
    if uncited:
        print("UNCITED references in the bibliography: %s" % uncited)
        return 2

    # build the reference list in citation order
    lines = []
    for i, k in enumerate(order, 1):
        r = dict(refs[k])
        lines.append(mod.nature_line(r, i))

    marker = "See `PLASMIDCALL_REFERENCES.md` for the formatted list"
    idx = text.index(marker)
    end = text.index("---", idx)
    text = text[:idx] + "\n".join(lines) + "\n\n" + text[end:]

    io.open("docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md", "w",
            encoding="utf-8", newline="\n").write(text)
    io.open("docs/manuscript/PLASMIDCALL_REFERENCE_ORDER.json", "w",
            encoding="utf-8", newline="\n").write(
        json.dumps({"n_cited": len(order), "journal_limit": 60,
                    "within_limit": len(order) <= 60,
                    "order": order,
                    "rule": "numbered in strict order of first appearance across text, Methods, "
                            "tables and figure legends"}, indent=1) + "\n")
    print("rendered: %d references cited, all bibliography entries used" % len(order))
    return 0


if __name__ == "__main__":
    sys.exit(main())
