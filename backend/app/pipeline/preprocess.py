"""Load photos, scans or PDFs and prepare each page for transcription."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()  # lets Pillow open iPhone .heic photos

MAX_EDGE = 2400  # px; enough detail for small subscripts
PDF_RENDER_EDGE = 2800  # render PDF pages a bit larger, then downscale for smooth strokes
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
SUPPORTED = IMAGE_TYPES | {".pdf"}


@dataclass
class SourcePage:
    label: str  # "lecture.pdf p3" or "photo.jpg"
    image: Image.Image


def parse_page_range(spec: str | None, count: int) -> list[int]:
    """'1-3,5' -> [0, 1, 2, 4] (0-based); None means all pages."""
    if not spec:
        return list(range(count))
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        start, _, end = part.partition("-")
        try:
            a, b = int(start), int(end or start)
        except ValueError:
            raise ValueError(f"bad page range {spec!r} (example: 1-3,5)")
        if not 1 <= a <= b:
            raise ValueError(f"bad page range {part!r}")
        pages += [n - 1 for n in range(a, min(b, count) + 1) if n - 1 not in pages]
    return pages


def load_pages(path: Path, page_range: str | None = None) -> list[SourcePage]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"{path.name}: unsupported file type (use {', '.join(sorted(SUPPORTED))})")
    if suffix != ".pdf":
        with Image.open(path) as raw:
            img = ImageOps.exif_transpose(raw).convert("RGB")  # phone photos are often stored sideways
        return [SourcePage(path.name, img)]

    pdf = pdfium.PdfDocument(path)
    try:
        pages = []
        for i in parse_page_range(page_range, len(pdf)):
            page = pdf[i]
            width, height = page.get_size()
            bitmap = page.render(scale=PDF_RENDER_EDGE / max(width, height))  # page rotation is applied
            pages.append(SourcePage(f"{path.name} p{i + 1}", bitmap.to_pil().convert("RGB")))
        return pages
    finally:
        pdf.close()


def normalize(img: Image.Image) -> Image.Image:
    """Resized, slightly contrast-boosted copy of the page."""
    img = img.copy()
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    return ImageOps.autocontrast(img, cutoff=1)  # lifts faint pencil and grey paper a little


def is_blank(img: Image.Image) -> bool:
    """True for empty pages (only paper, maybe faint ruling): fewer than 0.05% dark pixels."""
    grey = img.convert("L")
    grey.thumbnail((600, 600))
    dark = sum(grey.histogram()[:140])
    return dark < 0.0005 * grey.width * grey.height


def grid_overlay(img: Image.Image) -> Image.Image:
    """Copy of the page with labelled 10% grid lines, for reading figure coordinates."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    size = max(14, w // 60)
    for k in range(1, 10):
        x, y = w * k // 10, h * k // 10
        draw.line([(x, 0), (x, h)], fill=(0, 170, 220), width=2)
        draw.line([(0, y), (w, y)], fill=(0, 170, 220), width=2)
        draw.text((x + 4, 4), f".{k}", fill=(220, 0, 120), font_size=size)
        draw.text((4, y + 4), f".{k}", fill=(220, 0, 120), font_size=size)
    return out
