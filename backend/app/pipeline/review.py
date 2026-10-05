"""Review sheet for the remaining uncertain readings (\\unsure{...}).

For every mark: a crop of the original handwriting, a crop of the transcription with the mark
highlighted, an optional suggestion, and an answer line. Writes
    output/<name>/<name>-granskning.pdf   to look at
    output/<name>/<name>-granskning.txt   to fill in and send back

Optional input files in output/<name>/extras/:
    granskning-forslag.txt   "<nr>: <suggestion>"     shown under each mark
    granskning-utsnitt.txt   "<nr>: <top> <bottom>"   crop window in the original (fractions of
                                                       the page height) when the automatic one is off
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from app.pipeline.assemble import find_unsure, parse_page, preamble
from app.pipeline.compile import CompileResult, clean_aux, compile_tex
from app.pipeline.run import page_images

YELLOW = (255, 255, 140)  # \colorbox{yellow!55} renders close to this


@dataclass
class Mark:
    nr: int
    page: int
    reading: str        # LaTeX inside \unsure{...}
    position: float     # 0..1, how far down the page file the mark is


def marks(out_dir: Path) -> list[Mark]:
    found = []
    for n, img in enumerate(page_images(out_dir), 1):
        tex = img.with_suffix(".tex")
        if not tex.exists():
            continue
        page = parse_page(tex.read_text(encoding="utf-8"))
        body = page.body
        for m, reading in zip(re.finditer(r"\\unsure\{", body), find_unsure(body)):
            found.append(Mark(len(found) + 1, n, reading, m.start() / max(1, len(body))))
    return found


def as_text(reading: str) -> str:
    """The reading as printable text: words stay text, everything else is typeset as maths."""
    if "$" in reading or re.fullmatch(r"[A-Za-zÅÄÖåäöéÉ ,.]{3,}", reading):
        return reading
    return f"${reading}$"


SYMBOLS = {r"\varphi": "φ", r"\phi": "φ", r"\delta": "δ", r"\pi": "π", r"\ell": "ℓ", r"\gamma": "γ",
           r"\alpha": "α", r"\beta": "β", r"\theta": "θ", r"\infty": "∞", r"\sin": "sin", r"\cos": "cos",
           r"\operatorname{Im}": "Im", r"\operatorname{Re}": "Re", r"\le": "≤", r"\ge": "≥", r"\,": " ",
           r"\sum": "Σ", r"\cdot": "·", r"\min": "min", r"\max": "max", r"\ell og": "ℓog", "''": '"'}


def to_plain(tex: str) -> str:
    """Readable plain text for the answer file: φ instead of \\varphi, w̄ instead of \\bar{w}."""
    tex = re.sub(r"\\bar\s+([A-Za-z])", r"\\bar{\1}", tex)  # \bar z -> \bar{z}
    s = re.sub(r"\\(?:bar|overline)\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
               lambda m: to_plain(m.group(1)) + "\u0304" if len(to_plain(m.group(1))) == 1
               else "(" + to_plain(m.group(1)) + ")\u0304", tex)
    for k, v in sorted(SYMBOLS.items(), key=lambda kv: -len(kv[0])):
        s = s.replace(k, v)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\[a-zA-Z]+", "", s).replace("$", "").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def read_answers(txt: Path) -> dict[tuple[int, str], str]:
    """Answers already filled in, keyed by (page, reading) so renumbering cannot mix them up."""
    if not txt.exists():
        return {}
    answers, key = {}, None
    for line in txt.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*\d+\. Sida (\d+)\. Läst som: (.*)$", line)
        if m:
            key = (int(m.group(1)), m.group(2).strip())
        a = re.match(r"\s*Svar:\s*(.*)$", line)
        if a and key and a.group(1).strip():
            answers[key] = a.group(1).strip()
    return answers


def read_numbered(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(\d+)\s*:\s*(.*)$", line)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def yellow_boxes(pdf: Path, scale: float = 2.0) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Yellow highlight boxes in reading order: (pdf page index, (x0, y0, x1, y1) in pixels)."""
    doc = pdfium.PdfDocument(pdf)
    boxes = []
    for i in range(len(doc)):
        img = doc[i].render(scale=scale).to_pil().convert("RGB")
        w, h = img.size
        px = img.load()
        rows: dict[int, list[int]] = {}
        for y in range(0, h, 2):
            xs = [x for x in range(0, w, 2) if all(abs(a - b) <= 12 for a, b in zip(px[x, y], YELLOW))]
            if xs:
                rows[y] = xs
        # group consecutive rows into bands, then split each band into horizontal runs
        bands, current = [], []
        for y in sorted(rows):
            if current and y - current[-1] > 4:
                bands.append(current)
                current = []
            current.append(y)
        if current:
            bands.append(current)
        for band in bands:
            xs = sorted({x for y in band for x in rows[y]})
            runs, start = [], xs[0]
            for a, b in zip(xs, xs[1:]):
                if b - a > 12:
                    runs.append((start, a))
                    start = b
            runs.append((start, xs[-1]))
            for x0, x1 in runs:
                if x1 - x0 >= 6 and band[-1] - band[0] >= 6:
                    boxes.append((i, (x0, band[0], x1, band[-1])))
    return boxes


def crop_transcription(pdf: Path, box: tuple[int, tuple[int, int, int, int]], dest: Path) -> None:
    i, (x0, y0, x1, y1) = box
    img = pdfium.PdfDocument(pdf)[i].render(scale=2.0).to_pil().convert("RGB")
    w, h = img.size
    pad_y = 70
    region = img.crop((int(w * 0.08), max(0, y0 - pad_y), int(w * 0.92), min(h, y1 + pad_y)))
    region.save(dest)


def crop_original(page_img: Path, top: float, bottom: float, dest: Path) -> None:
    with Image.open(page_img) as img:
        w, h = img.size
        img.crop((0, int(max(0, top) * h), w, int(min(1, bottom) * h))).save(dest)


def build_review(out_dir: Path, title: str) -> tuple[CompileResult | None, Path, int]:
    found = marks(out_dir)
    txt = out_dir / f"{out_dir.name}-granskning.txt"
    previous = read_answers(txt)  # never throw away answers already written in the file
    if not found:  # keep an earlier answer file as a record
        if not txt.exists():
            txt.write_text("Inga osäkra läsningar kvar.\n", encoding="utf-8")
        return None, txt, 0

    main_pdf = out_dir / f"{out_dir.name}.pdf"
    boxes = yellow_boxes(main_pdf)
    if len(boxes) != len(found):
        raise ValueError(f"found {len(boxes)} highlights in {main_pdf.name} but {len(found)} marks in the "
                         "page files; rebuild the document first")
    suggestions = read_numbered(out_dir / "extras" / "granskning-forslag.txt")
    windows = read_numbered(out_dir / "extras" / "granskning-utsnitt.txt")
    crops = out_dir / "granskning"
    crops.mkdir(exist_ok=True)
    pages = page_images(out_dir)

    parts, lines = [], [
        f"Granskning av osäkra läsningar -- {title}",
        "Skriv efter 'Svar:' vad som står i originalet, eller 'ok' om läsningen stämmer.",
        "Lämna tomt om du inte vet. Skicka sedan filen (eller innehållet) till Claude.",
        "",
    ]
    for mark, box in zip(found, boxes):
        orig = crops / f"{mark.nr:02d}-original.png"
        if mark.nr in windows:
            top, bottom = (float(v) for v in windows[mark.nr].split()[:2])
        else:
            top, bottom = mark.position - 0.08, mark.position + 0.12
        crop_original(pages[mark.page - 1], top, bottom, orig)
        trans = crops / f"{mark.nr:02d}-transkription.png"
        crop_transcription(main_pdf, box, trans)
        suggestion = suggestions.get(mark.nr, "")
        parts.append(
            f"\\subsection*{{{mark.nr}. Sida {mark.page} \\quad \\normalfont\\small Läst som: \\unsure{{{as_text(mark.reading)}}}}}\n"
            f"\\noindent{{\\small\\color{{gray}} Original (originalanteckningarna sida {mark.page}):}}\\\\\n"
            f"\\includegraphics[width=\\linewidth,height=5.5cm,keepaspectratio]{{granskning/{orig.name}}}\\\\[0.4em]\n"
            f"{{\\small\\color{{gray}} Transkriptionen:}}\\\\\n"
            f"\\includegraphics[width=0.85\\linewidth,height=3.2cm,keepaspectratio]{{granskning/{trans.name}}}\n"
            + (f"\n\\textbf{{Förslag:}} {suggestion}\n" if suggestion else "")
            + "\n\\textbf{Svar:} \\hrulefill\n")
        lines += [f"{mark.nr}. Sida {mark.page}. Läst som: {to_plain(mark.reading)}"]
        if suggestion:
            lines.append(f"   Förslag: {to_plain(suggestion)}")
        lines += [f"   Svar: {previous.get((mark.page, to_plain(mark.reading)), '')}", ""]

    tex = out_dir / f"{out_dir.name}-granskning.tex"
    head = preamble().rstrip() + "\n\\begin{document}\n\\selectlanguage{swedish}\n"
    intro = (f"\\section*{{Granskning -- {title}}}\n"
             f"Här är de {len(found)} ställen som var svåra att läsa. Jämför originalet med "
             "transkriptionen och skriv svaret i \\texttt{" + txt.name.replace("_", "\\_") + "}.\n\n")
    tex.write_text(head + intro + "\n\\bigskip\n".join(parts) + "\n\\end{document}\n", encoding="utf-8")
    result = compile_tex(tex)
    clean_aux(tex)
    txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result, txt, len(found)
