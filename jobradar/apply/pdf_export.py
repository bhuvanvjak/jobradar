"""Renders a tailored resume as a clean, single-column PDF. Deliberately
plain formatting - no tables/graphics - because that's also what parses
most reliably through ATS software on real job portals. Uses fpdf2, which
is pure-Python (no system deps).
"""
from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

HEADING_RE = re.compile(r"^#{1,3}\s+(.*)")
BOLD_LINE_RE = re.compile(r"^\*\*(.*)\*\*$")

# fpdf2's core (non-embedded) Helvetica font only supports latin-1, which is
# narrower than what an LLM's writing (or a pasted resume) tends to contain -
# em dashes, curly quotes, ellipses. Normalize those to ASCII instead of
# crashing mid-render.
_UNICODE_FALLBACKS = {
    "—": "-", "–": "-",           # em dash, en dash
    "‘": "'", "’": "'",           # curly single quotes
    "“": '"', "”": '"',           # curly double quotes
    "…": "...",                        # ellipsis
    " ": " ",                          # non-breaking space
}


def _sanitize(text: str) -> str:
    for bad, good in _UNICODE_FALLBACKS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def markdown_to_pdf(md_text: str, out_path: Path) -> Path:
    # Strip HTML comments so instructional notes in a resume template never
    # end up in a PDF actually sent to an employer.
    md_text = re.sub(r"<!--.*?-->", "", md_text, flags=re.DOTALL)

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(18, 15, 18)

    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            pdf.ln(3)
            continue

        heading = HEADING_RE.match(line)
        bold = BOLD_LINE_RE.match(line)
        text = line

        if heading:
            text = heading.group(1)
            pdf.set_font("Helvetica", "B", 13 if line.startswith("# ") else 11)
        elif bold:
            text = bold.group(1)
            pdf.set_font("Helvetica", "B", 10)
        elif line.startswith(("- ", "* ")):
            # ASCII hyphen, not a unicode bullet - the core PDF font can't
            # render one anyway, and plain hyphens parse fine through ATS.
            text = "  - " + line[2:]
            pdf.set_font("Helvetica", "", 10)
        else:
            pdf.set_font("Helvetica", "", 10)

        text = text.replace("**", "").replace("__", "")
        text = _sanitize(text)
        # new_x/new_y must be set explicitly: fpdf2's default (new_x=RIGHT)
        # leaves the cursor at the right margin instead of wrapping to the
        # next line, which breaks every subsequent multi_cell call.
        pdf.multi_cell(0, 5.5, text, align="L", new_x="LMARGIN", new_y="NEXT")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path
