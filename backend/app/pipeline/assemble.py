"""Turn transcribed pages into a full .tex document and crop figure images.

Each transcribed page is a file pN.tex: a few header comments, then the LaTeX body.

    % language: swedish
    % figure: fig1 0.10 0.35 0.60 0.70
    \\section{Kraft}
    ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from app.pipeline.navigation import add_navigation

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
FIGURE_PADDING = 0.008  # small margin around figure boxes (fraction of page); dense pages need it small

LANGUAGES = {"english", "swedish"}


@dataclass
class Figure:
    id: str
    bbox: list[float]  # [x0, y0, x1, y1], fractions of page width/height


@dataclass
class Page:
    body: str
    language: str = "english"
    figures: list[Figure] = field(default_factory=list)
    first_line: int = 1  # line in the pN.tex file where the body starts

    @property
    def uncertain(self) -> list[str]:
        return find_unsure(self.body)


def parse_page(text: str) -> Page:
    """Read a pN.tex page file: header comments (language, figures), then the body."""
    page = Page(body="")
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("%")):
        m = re.match(r"\s*%\s*(language|figure)\s*:\s*(.*)$", lines[i])
        if m and m.group(1) == "language":
            page.language = m.group(2).strip().lower()
        elif m:
            parts = m.group(2).split()
            try:
                if len(parts) != 5:
                    raise ValueError
                page.figures.append(Figure(parts[0], [float(x) for x in parts[1:]]))
            except ValueError:
                raise ValueError(f"bad figure line: {lines[i].strip()!r} "
                                 "(expected: % figure: fig1 x0 y0 x1 y1)")
        i += 1
    page.first_line = i + 1
    page.body = clean_body("\n".join(lines[i:]))
    return page


def find_unsure(body: str) -> list[str]:
    """Contents of every \\unsure{...}, with nested braces handled."""
    found = []
    for m in re.finditer(r"\\unsure\{", body):
        depth, j = 1, m.end()
        while j < len(body) and depth:
            depth += {"{": 1, "}": -1}.get(body[j], 0)
            j += 1
        found.append(body[m.end() : j - 1])
    return found


def preamble() -> str:
    return (TEMPLATES / "preamble.tex").read_text(encoding="utf-8")


def clean_body(body: str) -> str:
    """Strip anything that belongs in the preamble, in case it was added anyway."""
    m = re.search(r"\\begin\{document\}(.*?)(\\end\{document\}|$)", body, re.S)
    if m:
        body = m.group(1)
    body = re.sub(r"^\s*```(?:latex|tex)?\s*\n|\n\s*```\s*$", "", body)
    body = re.sub(r"^\s*\\(documentclass|usepackage)\b.*$", "", body, flags=re.M)
    return body.strip()


def page_body(page: Page, index: int, total: int) -> str:
    lang = page.language if page.language in LANGUAGES else "english"
    parts = [f"\\selectlanguage{{{lang}}}", page.body]
    if total > 1 and index < total - 1:
        parts.append(f"\\pagebreakmarker{{{index + 1}}}")
    return "\n".join(parts)


def build_document(pages: list[Page], title: str = "", page_numbers: list[int] | None = None) -> str:
    """Full .tex source. The body starts two lines after \\begin{document} (after \\selectlanguage).

    Long documents (3+ sections) get a table of contents, a list of theorems and links from
    references like "Sats 9.18" to the theorem titled with that number.
    """
    page_numbers = page_numbers or list(range(1, len(pages) + 1))
    bodies = [page_body(p, i, len(pages)) for i, p in enumerate(pages)]
    long_doc = sum(len(re.findall(r"\\section\{", b)) for b in bodies) >= 3
    if long_doc:
        bodies = add_navigation(bodies, page_numbers)
    head = preamble().rstrip() + "\n\n\\begin{document}\n"
    if title:
        head += f"\\section*{{{title}}}\n"
    if long_doc:
        lang = pages[0].language if pages[0].language in LANGUAGES else "english"
        head += f"\\selectlanguage{{{lang}}}\\tableofcontents\n\\listoftheorems\n\\newpage\n"
    return head + "\n\n".join(bodies) + "\n\\end{document}\n"


def body_line_offset(tex: str) -> int:
    """Line number of \\begin{document}, for mapping compiler errors back to the page body."""
    return tex[: tex.index("\\begin{document}")].count("\n") + 1


def crop_figures(image: Image.Image, figures: list[Figure], out_dir: Path, prefix: str = "") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = image.size
    written = []
    for fig in figures:
        if len(fig.bbox) != 4:
            continue
        x0, y0, x1, y1 = fig.bbox
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        box = (
            max(0, int((x0 - FIGURE_PADDING) * w)),
            max(0, int((y0 - FIGURE_PADDING) * h)),
            min(w, int((x1 + FIGURE_PADDING) * w)),
            min(h, int((y1 + FIGURE_PADDING) * h)),
        )
        if box[2] - box[0] < 10 or box[3] - box[1] < 10:
            continue
        path = out_dir / f"{prefix}{fig.id}.png"
        whiten_paper(image.crop(box)).save(path)
        written.append(path)
    return written


def whiten_paper(img: Image.Image, threshold: int = 205) -> Image.Image:
    """Turn light paper tones (cream, grey, grid lines) white so figures match the PDF page."""
    grey = img.convert("L")
    mask = grey.point(lambda v: 255 if v >= threshold else 0)
    out = img.copy()
    out.paste((255, 255, 255), mask=mask)
    return out
