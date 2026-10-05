"""The pipeline, in two steps around the transcription that Claude Code does in between.

prepare: photos/PDFs -> output/<name>/pages/pN.jpg (+ pN-grid.jpg for reading figure positions)
         (Claude reads each pN.jpg and writes pN.tex)
build:   pN.tex files -> cropped figures -> <name>.tex -> <name>.pdf, or per-page errors to fix
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from app.pipeline.assemble import Page, body_line_offset, build_document, crop_figures, parse_page
from app.pipeline.compile import clean_aux, compile_tex
from app.pipeline.preprocess import grid_overlay, is_blank, load_pages, normalize


@dataclass
class PreparedPage:
    number: int
    source: str  # "lecture.pdf p3" or "photo.jpg"
    image: Path
    grid: Path
    transcription: Path


@dataclass
class PrepareResult:
    pages: list[PreparedPage]
    blank: list[str] = field(default_factory=list)  # skipped empty pages
    stale: list[str] = field(default_factory=list)  # old transcriptions set aside (page changed)


@dataclass
class BuildResult:
    tex: Path
    pdf: Path | None
    ok: bool
    page_errors: dict[int, list[str]] = field(default_factory=dict)  # page -> body-relative errors
    errors: list[str] = field(default_factory=list)                 # whole-document errors
    uncertain: dict[int, list[str]] = field(default_factory=dict)
    missing: list[int] = field(default_factory=list)                 # pages not transcribed yet


def prepare_pages(files: list[Path], out_dir: Path, page_range: str | None = None,
                  keep_blank: bool = False) -> PrepareResult:
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    sources_file = out_dir / "sources.json"
    old_sources = json.loads(sources_file.read_text()) if sources_file.exists() else []
    for old in pages_dir.glob("p*.jpg"):  # a re-run replaces the page images
        old.unlink()

    result = PrepareResult([])
    for f in files:
        for src in load_pages(f, page_range):
            if not keep_blank and is_blank(src.image):
                result.blank.append(src.label)
                continue
            n = len(result.pages) + 1
            page = PreparedPage(n, src.label, pages_dir / f"p{n}.jpg", pages_dir / f"p{n}-grid.jpg",
                                pages_dir / f"p{n}.tex")
            img = normalize(src.image)
            img.save(page.image, quality=92)
            grid_overlay(img).save(page.grid, quality=85)
            result.pages.append(page)

    # Earlier transcriptions follow their source page to its new number (e.g. when a PDF is
    # added in front). Ones whose page is no longer included are set aside as pN.stale.tex.
    labels = [p.source for p in result.pages]
    earlier: dict[str, str] = {}
    for tex in pages_dir.glob("p*.tex"):
        if not re.fullmatch(r"p\d+", tex.stem):
            continue
        n = int(tex.stem[1:])
        old_label = old_sources[n - 1] if n <= len(old_sources) else None
        if old_label in labels:
            earlier[old_label] = tex.read_text(encoding="utf-8")
            tex.unlink()
        else:
            tex.rename(tex.with_name(f"{tex.stem}.stale.tex"))
            result.stale.append(f"p{n}.tex ({old_label or 'unknown page'})")
    for page in result.pages:
        if page.source in earlier:
            page.transcription.write_text(earlier[page.source], encoding="utf-8")
    sources_file.write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def page_images(out_dir: Path) -> list[Path]:
    pages = out_dir / "pages"
    return sorted((p for p in pages.glob("p*.jpg") if re.fullmatch(r"p\d+", p.stem)),
                  key=lambda p: int(p.stem[1:]))


def build(out_dir: Path, title: str = "", partial: bool = False) -> BuildResult:
    """Build the document. With partial=True, build only the transcribed pages before the first
    missing one (for checking progress on a long document)."""
    tex_path = out_dir / f"{out_dir.name}.tex"
    images = page_images(out_dir)
    if not images:
        raise ValueError(f"no prepared pages in {out_dir / 'pages'}; run prepare first")

    missing = [n for n, img in enumerate(images, 1) if not img.with_suffix(".tex").exists()]
    if missing and partial and missing[0] > 1:
        images = images[: missing[0] - 1]
    elif missing:
        return BuildResult(tex_path, None, False, missing=missing)

    pages: list[Page] = []
    figures_dir = out_dir / "figures"
    for old in figures_dir.glob("*.png"):
        old.unlink()
    for n, img_path in enumerate(images, 1):
        page = parse_page(img_path.with_suffix(".tex").read_text(encoding="utf-8"))
        prefix_figures(page, f"p{n}-")
        with Image.open(img_path) as img:
            crop_figures(img, page.figures, figures_dir)
        pages.append(page)

    uncertain = {n: p.uncertain for n, p in enumerate(pages, 1) if p.uncertain}
    result = write_and_compile(pages, tex_path, title)
    if result.ok:
        clean_aux(tex_path)
        return BuildResult(tex_path, result.pdf, True, uncertain=uncertain)

    page_errors = check_pages(pages, out_dir)
    clean_aux(tex_path)
    return BuildResult(tex_path, None, False, page_errors=page_errors,
                       errors=[] if page_errors else result.errors, uncertain=uncertain)


def load_transcribed(out_dir: Path) -> list[Page]:
    """All transcribed pages, figure ids prefixed like in the built document (no cropping)."""
    pages = []
    for n, img_path in enumerate(page_images(out_dir), 1):
        tex = img_path.with_suffix(".tex")
        if not tex.exists():
            break
        page = parse_page(tex.read_text(encoding="utf-8"))
        prefix_figures(page, f"p{n}-")
        pages.append(page)
    return pages


def write_and_compile(pages: list[Page], tex_path: Path, title: str = ""):
    tex_path.write_text(build_document(pages, title), encoding="utf-8")
    return compile_tex(tex_path)


def prefix_figures(page: Page, prefix: str) -> None:
    """Give figure ids a per-page prefix (p1-fig1) so pages don't overwrite each other's images,
    and size each figure like on the original page: \\notefigure[0.33]{p1-fig1}{...}."""
    renames, widths = {}, {}
    for fig in page.figures:
        new_id = prefix + re.sub(r"[^A-Za-z0-9-]", "", fig.id)
        renames[fig.id] = new_id
        if len(fig.bbox) == 4:
            # The original page's writing spans roughly 90% of its width.
            widths[new_id] = min(1.0, max(0.15, abs(fig.bbox[2] - fig.bbox[0]) / 0.9))
        fig.id = new_id

    def replace(m: re.Match) -> str:
        new_id = renames.get(m.group(1), prefix + m.group(1))
        width = f"[{widths[new_id]:.2f}]" if new_id in widths else ""
        return f"\\notefigure{width}{{{new_id}}}"
    page.body = re.sub(r"\\notefigure(?:\[[^\]]*\])?\{([^}]*)\}", replace, page.body)


def check_pages(pages: list[Page], out_dir: Path) -> dict[int, list[str]]:
    """Compile each page on its own to find which ones fail, with errors relative to that page."""
    failing = {}
    for n, page in enumerate(pages, 1):
        # No leading dot: TeX refuses to write files whose names start with one.
        check = out_dir / f"_check-p{n}.tex"
        result = write_and_compile([page], check)
        if not result.ok:
            failing[n] = body_relative_errors(result.errors, body_line_offset(check.read_text()),
                                              page.first_line)
        for ext in (".tex", ".pdf", ".log"):
            check.with_suffix(ext).unlink(missing_ok=True)
        clean_aux(check)
    return failing


def body_relative_errors(errors: list[str], offset: int, first_line: int = 1) -> list[str]:
    """Rewrite document line numbers as line numbers in the page's pN.tex file.

    In the compiled document the body starts two lines after \\begin{document} (after
    \\selectlanguage); in the page file it starts after the header comments, at first_line.
    """
    def shift(n: str) -> int:
        return max(1, int(n) - offset - 1) + first_line - 1
    out = []
    for e in errors:
        e = re.sub(r"[^\s:]*\.tex:(\d+):", lambda m: f"line {shift(m.group(1))}:", e)
        e = re.sub(r"\bl\.(\d+)", lambda m: f"line {shift(m.group(1))}", e)
        out.append(e)
    return out
