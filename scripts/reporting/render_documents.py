# -*- coding: utf-8 -*-
"""Render the manuscript, preprint, Supplementary Information and cover letters to DOCX and PDF.

DOCX is produced by pandoc. PDF is produced directly with reportlab so that fonts are embedded,
tables paginate with repeated headers, and figures are placed at a controlled size. Both routes
read the same markdown, so the two forms cannot diverge in content.
"""
import io, os, re, sys, json, hashlib

import matplotlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
                                TableStyle, Image, KeepTogether, PageBreak, HRFlowable)
from reportlab.lib.utils import ImageReader

FONTDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
FONTS = [("DejaVuSerif", "DejaVuSerif.ttf"), ("DejaVuSerif-Bold", "DejaVuSerif-Bold.ttf"),
         ("DejaVuSerif-Italic", "DejaVuSerif-Italic.ttf"),
         ("DejaVuSerif-BoldItalic", "DejaVuSerif-BoldItalic.ttf"),
         ("DejaVuSans", "DejaVuSans.ttf"), ("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"),
         ("DejaVuSansMono", "DejaVuSansMono.ttf")]
for name, fn in FONTS:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONTDIR, fn)))
pdfmetrics.registerFontFamily("DejaVuSerif", normal="DejaVuSerif", bold="DejaVuSerif-Bold",
                              italic="DejaVuSerif-Italic", boldItalic="DejaVuSerif-BoldItalic")

PW, PH = A4
ML = MR = 20 * mm
MT = 18 * mm
MB = 18 * mm
CW = PW - ML - MR

S = {
 "body": ParagraphStyle("body", fontName="DejaVuSerif", fontSize=9.2, leading=13.0,
                        spaceAfter=5.2, alignment=TA_LEFT),
 "h1": ParagraphStyle("h1", fontName="DejaVuSans-Bold", fontSize=15, leading=19,
                      spaceBefore=6, spaceAfter=9, textColor=colors.HexColor("#10263a")),
 "h2": ParagraphStyle("h2", fontName="DejaVuSans-Bold", fontSize=11.5, leading=15,
                      spaceBefore=13, spaceAfter=6, textColor=colors.HexColor("#1f4e79")),
 "h3": ParagraphStyle("h3", fontName="DejaVuSans-Bold", fontSize=9.8, leading=13,
                      spaceBefore=9, spaceAfter=4, textColor=colors.HexColor("#333333")),
 "h4": ParagraphStyle("h4", fontName="DejaVuSans-Bold", fontSize=9.2, leading=12,
                      spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#444444")),
 "quote": ParagraphStyle("quote", fontName="DejaVuSerif-Italic", fontSize=8.6, leading=12,
                         leftIndent=8, spaceAfter=6, textColor=colors.HexColor("#404040")),
 "li": ParagraphStyle("li", fontName="DejaVuSerif", fontSize=9.2, leading=12.6,
                      leftIndent=12, bulletIndent=3, spaceAfter=2.4,
                      bulletFontName="DejaVuSerif", bulletFontSize=9.2),
 "code": ParagraphStyle("code", fontName="DejaVuSansMono", fontSize=7.6, leading=10.2,
                        leftIndent=8, spaceAfter=6, backColor=colors.HexColor("#f4f5f7")),
 "cell": ParagraphStyle("cell", fontName="DejaVuSerif", fontSize=6.6, leading=8.4),
 "cellh": ParagraphStyle("cellh", fontName="DejaVuSans-Bold", fontSize=6.6, leading=8.4,
                         textColor=colors.white),
 "cap": ParagraphStyle("cap", fontName="DejaVuSerif", fontSize=8.2, leading=11,
                       spaceBefore=3, spaceAfter=9, textColor=colors.HexColor("#333333")),
}


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


ESCAPES = {"\\*": "\x01", "\\|": "\x02", "\\_": "\x03", "\\#": "\x04", "\\[": "\x05"}
UNESCAPES = {"\x01": "*", "\x02": "|", "\x03": "_", "\x04": "#", "\x05": "["}


def inline(t):
    """Markdown inline -> reportlab mini-HTML. Backslash escapes are protected first, so that a
    literal asterisk cannot be swallowed by the emphasis patterns."""
    for a, b in ESCAPES.items():
        t = t.replace(a, b)
    t = esc(t)
    t = re.sub(r"`([^`]+)`", r'<font face="DejaVuSansMono" size="7.8">\1</font>', t)
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="#1f4e79">\1</link>', t)
    t = re.sub(r"\^([0-9,\u2013]+)\^", r'<super>\1</super>', t)
    t = re.sub(r"\^(\d)\^", r"<super>\1</super>", t)
    for a, b in UNESCAPES.items():
        t = t.replace(a, b)
    return t


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    out, cur, i = [], "", 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if line[i] == "|":
            out.append(cur)
            cur = ""
            i += 1
            continue
        cur += line[i]
        i += 1
    out.append(cur)
    return [c.strip() for c in out]


def make_table(rows, base_dir):
    header, body = rows[0], rows[1:]
    ncol = max(len(r) for r in rows)
    header = header + [""] * (ncol - len(header))
    body = [r + [""] * (ncol - len(r)) for r in body]
    # Column widths: every column must be at least as wide as its widest unbreakable token, so
    # headers and numeric values never split mid-word. Remaining width is then shared in
    # proportion to total cell content.
    def tokw(txt, font, size):
        import re as _re
        plain = _re.sub(r"[*`\\]", "", txt)
        toks = plain.split()
        return max([pdfmetrics.stringWidth(t, font, size) for t in toks] or [0])

    def fullw(txt, font, size):
        import re as _re
        return pdfmetrics.stringWidth(_re.sub(r"[*`\\]", "", txt), font, size)

    PAD = 7.0
    minw, prefw = [], []
    for c in range(ncol):
        m = tokw(header[c], "DejaVuSans-Bold", 6.6)
        f = fullw(header[c], "DejaVuSans-Bold", 6.6)
        for r in body:
            m = max(m, tokw(r[c], "DejaVuSerif", 6.6))
            f = max(f, fullw(r[c], "DejaVuSerif", 6.6))
        minw.append(min(m + PAD, CW * 0.30))
        prefw.append(min(f + PAD, CW * 0.42))
    if sum(minw) >= CW:                       # cannot honour the minima; fall back proportionally
        tot = float(sum(minw))
        widths = [CW * x / tot for x in minw]
    else:
        slack = CW - sum(minw)
        extra = [max(0.0, prefw[c] - minw[c]) for c in range(ncol)]
        te = float(sum(extra)) or 1.0
        widths = [minw[c] + slack * (extra[c] / te if sum(extra) > 0 else 1.0 / ncol)
                  for c in range(ncol)]
        # any width left over after preferences are met is spread evenly
        rem = CW - sum(widths)
        if rem > 0.5:
            widths = [x + rem / ncol for x in widths]
    data = [[Paragraph(inline(h), S["cellh"]) for h in header]]
    for r in body:
        data.append([Paragraph(inline(c), S["cell"]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b9c4cf")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f5f7f9")]),
    ]))
    return t


def md_to_flowables(md, base_dir):
    flow = []
    lines = md.split("\n")
    i = 0
    para = []

    def flush():
        if para:
            txt = " ".join(x.strip() for x in para).strip()
            if txt:
                flow.append(Paragraph(inline(txt), S["body"]))
            del para[:]

    while i < len(lines):
        L = lines[i]
        st = L.strip()
        if not st:
            flush()
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", st)
        if m:
            flush()
            lvl = len(m.group(1))
            flow.append(Paragraph(inline(m.group(2)), S["h%d" % lvl]))
            i += 1
            continue
        if st in ("---", "***", "___"):
            flush()
            flow.append(Spacer(1, 3))
            flow.append(HRFlowable(width="100%", thickness=0.5,
                                   color=colors.HexColor("#c9d1d9")))
            flow.append(Spacer(1, 5))
            i += 1
            continue
        if st.startswith("```"):
            flush()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            flow.append(Paragraph("<br/>".join(esc(b) for b in buf).replace(" ", "&nbsp;"),
                                  S["code"]))
            continue
        if st.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            flow.append(Paragraph(inline(" ".join(buf)), S["quote"]))
            continue
        im = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", st)
        if im:
            flush()
            path = os.path.join(base_dir, im.group(2))
            if os.path.exists(path):
                iw, ih = ImageReader(path).getSize()
                w = min(CW, iw * 0.12)
                h = w * ih / float(iw)
                maxh = PH - MT - MB - 60
                if h > maxh:
                    h = maxh
                    w = h * iw / float(ih)
                flow.append(Spacer(1, 4))
                flow.append(Image(path, width=w, height=h))
                flow.append(Spacer(1, 3))
            i += 1
            continue
        if st.startswith("|") and i + 1 < len(lines) and re.match(
                r"^\|[\s:\-|]+\|?\s*$", lines[i + 1].strip()):
            flush()
            rows = [split_row(st)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            flow.append(Spacer(1, 2))
            flow.append(make_table(rows, base_dir))
            flow.append(Spacer(1, 7))
            continue
        lm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", L)
        if lm:
            flush()
            bullet = "\u2022" if lm.group(2) in "-*+" else lm.group(2)
            body = lm.group(3)
            j = i + 1
            while j < len(lines) and lines[j].startswith("  ") and lines[j].strip() \
                    and not re.match(r"^(\s*)([-*+]|\d+\.)\s+", lines[j]):
                body += " " + lines[j].strip()
                j += 1
            i = j
            flow.append(Paragraph(inline(body), S["li"], bulletText=bullet))
            continue
        para.append(L)
        i += 1
    flush()
    return flow


class Doc(BaseDocTemplate):
    def __init__(self, path, footer, **kw):
        BaseDocTemplate.__init__(self, path, pagesize=A4, leftMargin=ML, rightMargin=MR,
                                 topMargin=MT, bottomMargin=MB, **kw)
        self.footer = footer
        frame = Frame(ML, MB, CW, PH - MT - MB, id="F")
        self.addPageTemplates([PageTemplate(id="P", frames=[frame], onPage=self._page)])

    def _page(self, canv, doc):
        canv.saveState()
        canv.setFont("DejaVuSans", 6.8)
        canv.setFillColor(colors.HexColor("#7a8590"))
        canv.drawString(ML, 10 * mm, self.footer)
        canv.drawRightString(PW - MR, 10 * mm, "%d" % doc.page)
        canv.restoreState()


def render_pdf(md_path, pdf_path, footer, title):
    md = io.open(md_path, encoding="utf-8").read()
    base = os.path.dirname(os.path.abspath(md_path))
    doc = Doc(pdf_path, footer, title=title, author="Vahhab Piranfar")
    doc.build(md_to_flowables(md, base))
    return os.path.getsize(pdf_path)


def render_docx(md_path, docx_path, resource_dir):
    import pypandoc
    pypandoc.convert_file(md_path, "docx", outputfile=docx_path,
                          extra_args=["--resource-path=%s" % resource_dir, "--standalone",
                                      "--wrap=none"])
    return os.path.getsize(docx_path)


def sha(p):
    return hashlib.sha256(io.open(p, "rb").read()).hexdigest()


def main(jobs):
    out = []
    for md, stem, footer, title, docx in jobs:
        d = os.path.dirname(stem)
        if d:
            os.makedirs(d, exist_ok=True)
        p = stem + ".pdf"
        n = render_pdf(md, p, footer, title)
        rec = {"source": md, "pdf": p, "pdf_bytes": n, "pdf_sha256": sha(p)}
        print("  %-58s %8d bytes" % (os.path.basename(p), n))
        if docx:
            q = stem + ".docx"
            m = render_docx(md, q, os.path.dirname(os.path.abspath(md)))
            rec.update({"docx": q, "docx_bytes": m, "docx_sha256": sha(q)})
            print("  %-58s %8d bytes" % (os.path.basename(q), m))
        out.append(rec)
    return out


if __name__ == "__main__":
    JOBS = json.load(io.open(sys.argv[1], encoding="utf-8"))
    res = main([tuple(j) for j in JOBS])
    io.open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(
        json.dumps({"rendered_utc": "2026-08-24", "documents": res}, indent=1) + "\n")
    print("rendered %d documents" % len(res))
