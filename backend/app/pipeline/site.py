"""Static website for a transcribed document: the notes and the study material in one page.

    ./notes site <name> [-t title]
        site/<name>/index.html      the page; figures in site/<name>/figures/ (GitHub Pages etc.)
        site/<name>/artifact.html   the same page with the figures inlined and without the
                                    <html>/<head> wrapper, for publishing as one file
        site/index.html             lists every document built so far

LaTeX -> HTML with pandoc. The maths stays TeX and MathJax renders it in the browser, one view at
a time (a lecture, the exercises, ...), so the page opens quickly despite thousands of formulas.
Views: Hem, one per \\section of the notes, Satser och definitioner, Bevislista, Övningar,
Flashcards and one per hand-written extras/*.tex (formelblad, rättelser, ...).
"""

from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops

from app.pipeline.assemble import preamble
from app.pipeline.compile import clean_aux, compile_tex
from app.pipeline.extras import Document, bevislista_body, braced, exercises, load, load_deck
from app.pipeline.navigation import add_navigation

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "site"

# xcolor specs used in the notes -> ink names (CSS classes ink-<name>, coloured per theme)
INKS = {"magenta!80!black": "magenta", "red!70!black": "red", "red!55!black": "red",
        "blue!60!black": "blue", "green!50!black": "green", "rattat": "rattat"}

BOX_KINDS = {"theorem": ("Sats", "Theorem"), "definition": ("Definition", "Definition"),
             "example": ("Exempel", "Example"), "note": ("Anmärkning", "Remark"), "framed": ("", "")}

# Pandoc expands these, in text and in maths alike.
MACROS = r"""
\newcommand{\rattat}[2]{{#1}\textsuperscript{\textcolor{rattat}{†}}}
\newcommand{\notefigure}[3][0.5]{\includegraphics[width=#1\linewidth]{figures/#2.png}}
\newcommand{\theoremindex}[1]{}
\newcommand{\exbox}[1]{\textbf{⟦#1⟧}}
\newcommand{\unsure}[1]{#1}
\newcommand{\dag}{†}
\newcommand{\SI}[2]{#1\,#2}
\newcommand{\si}[1]{#1}
\newcommand{\num}[1]{#1}
\newcommand{\metre}{m}
\newcommand{\second}{s}
\newcommand{\per}{/}
\newcommand{\squared}{\textsuperscript{2}}
"""

SEGMENT = "@@SEG {}@@"
SEGMENT_HTML = re.compile(r"<p>@@SEG (\S+)@@</p>\n?")
PAGE_MARK = "@@SIDA {}@@"
BOX_START = re.compile(r"\\begin\{(theorem|definition|example|note|framed)\}"
                       r"(?:\[((?:[^\[\]]|\[[^\]]*\])*)\])?")


# --- LaTeX before pandoc ----------------------------------------------------------------------

def math_regions(tex: str) -> list[tuple[int, int]]:
    """Spans of tex that are maths: $..$, $$..$$, \\(..\\), \\[..\\] and align-like environments."""
    regions, i, n = [], 0, len(tex)
    pairs = [("$$", "$$"), ("\\[", "\\]"), ("\\(", "\\)")]
    while i < n:
        if tex.startswith("\\$", i):
            i += 2
            continue
        m = re.match(r"\\begin\{(align\*?|equation\*?|gather\*?|multline\*?)\}", tex[i:i + 30])
        if m:
            end = tex.find(f"\\end{{{m.group(1)}}}", i)
            end = n if end < 0 else end + len(m.group(1)) + 6
            regions.append((i, end))
            i = end
            continue
        for open_, close in pairs:
            if tex.startswith(open_, i):
                end = tex.find(close, i + len(open_))
                end = n if end < 0 else end + len(close)
                regions.append((i, end))
                i = end
                break
        else:
            if tex[i] == "$":
                j = i + 1
                while j < n and (tex[j] != "$" or tex[j - 1] == "\\"):
                    j += 1
                regions.append((i, j + 1))
                i = j + 1
            else:
                i += 1
    return regions


def circled(ch: str) -> str:
    if ch.isdigit() and 1 <= int(ch) <= 20:
        return chr(0x2460 + int(ch) - 1)
    if len(ch) == 1 and "a" <= ch <= "z":
        return chr(0x24D0 + ord(ch) - ord("a"))
    if len(ch) == 1 and "A" <= ch <= "Z":
        return chr(0x24B6 + ord(ch) - ord("A"))
    return f"({ch})"


def enum_label(m: re.Match) -> str:
    """enumitem's [label=\\alph*)] -> the enumerate-package form [a)] that pandoc reads."""
    lab = re.search(r"label=([^,]*)", m.group(1))
    if not lab:
        return "\\begin{enumerate}"
    lab = re.sub(r"\\textcircled\{(.*?)\}", r"(\1)", lab.group(1))
    for k, v in ((r"\alph*", "a"), (r"\Alph*", "A"), (r"\roman*", "i"), (r"\Roman*", "I"),
                 (r"\arabic*", "1")):
        lab = lab.replace(k, v)
    return f"\\begin{{enumerate}}[{lab}]"


def prepare_tex(tex: str) -> str:
    """Rewrite what pandoc would drop or get wrong: box titles, text-mode \\fbox, \\textcircled."""
    tex = re.sub(r"\\selectlanguage\{\w+\}", "", tex)
    tex = tex.replace("\\hfill\\break", "\\\\")
    tex = re.sub(r"\\begin\{enumerate\}\[([^\]]*)\]", enum_label, tex)
    tex = re.sub(r"\\(begin|end)\{multicols\}(\{\d+\})?", "", tex)
    tex = re.sub(r"\\begin\{(description|itemize)\}\[[^\]]*\]", r"\\begin{\1}", tex)
    tex = re.sub(r"\\pagebreakmarker\{\d+\}", "", tex)
    tex = re.sub(r"\\textcircled\{\\?(\w+)\}", lambda m: circled(m.group(1)), tex)
    tex = BOX_START.sub(lambda m: f"\\begin{{{m.group(1)}}}\n\n\\textbf{{⟪{m.group(2) or ''}⟫}}\n\n", tex)
    maths = math_regions(tex)
    out, last = [], 0
    for m in re.finditer(r"\\fbox\{", tex):
        if not any(a <= m.start() < b for a, b in maths):
            out += [tex[last:m.start()], "\\exbox{"]
            last = m.end()
    return "".join(out) + tex[last:]


def pandoc(segments: dict[str, str]) -> dict[str, str]:
    """Convert many LaTeX snippets with one pandoc run: {key: tex} -> {key: html}."""
    src = MACROS + "".join(f"\n\n{SEGMENT.format(k)}\n\n{prepare_tex(t)}\n" for k, t in segments.items())
    out = subprocess.run(["pandoc", "-f", "latex", "-t", "html", "--mathjax", "--wrap=none",
                          "--shift-heading-level-by=1"], input=src, capture_output=True,
                         text=True, check=True).stdout
    parts = SEGMENT_HTML.split(out)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


# --- HTML after pandoc ------------------------------------------------------------------------

@dataclass
class Box:
    id: str
    kind: str        # theorem, definition, ...
    title: str       # HTML, may contain maths
    page: int | None
    excerpt: str = ""  # start of the box text, for boxes without a title


@dataclass
class View:
    key: str
    title: str
    html: str
    group: str = "study"                       # "notes" or "study"
    boxes: list[Box] = field(default_factory=list)


def ink(spec: str) -> str:
    return INKS.get(spec.strip(), "plain")


def fix_math(m: re.Match) -> str:
    tex = m.group(2)
    tex = re.sub(r"\\textcolor\{([^}]*)\}\{", lambda c: f"\\class{{ink-{ink(c.group(1))}}}{{", tex)
    tex = re.sub(r"\\hyperlink\{[^}]*\}\{([^}]*)\}", r"\1", tex)
    tex = re.sub(r"\\hypertarget\{[^}]*\}\{\}", "", tex)
    return f'<span class="math {m.group(1)}">{tex}</span>'


class Polisher:
    """Turns pandoc output into the site's markup. Keeps one box counter for the whole site."""

    def __init__(self, lang: str):
        self.lang = lang
        self.count = 0
        self.page = None    # last page marker seen, for boxes before a view's first marker

    def text(self, s: str) -> str:
        """Inline fixes that need no context: maths, ink colours, exercise numbers, proofs."""
        s = re.sub(r'<span class="math (inline|display)">(.*?)</span>', fix_math, s, flags=re.S)
        s = re.sub(r'style="color: ([^"]+)"', lambda m: f'class="ink-{ink(m.group(1))}"', s)
        s = re.sub(r"<strong>⟦(.*?)⟧</strong>", r'<span class="exnum">\1</span>', s, flags=re.S)
        s = re.sub(r"<p>@@SIDA (\d+)@@</p>",
                   r'<div class="sida" id="sida-\1"><span>sida \1</span></div>', s)
        if self.lang == "swedish":
            s = s.replace("<em>Proof.</em>", "<em>Bevis.</em>")
        return re.sub(r"(<table>.*?</table>)", r'<div class="table-wrap">\1</div>', s, flags=re.S)

    def __call__(self, view: View) -> View:
        s = self.text(view.html)
        boxes: list[Box] = []

        def box(m: re.Match) -> str:
            self.count += 1
            kind, title = m.group(1), m.group(2).strip()
            label = BOX_KINDS[kind][0 if self.lang == "swedish" else 1]
            page = max((int(p) for p in re.findall(r'id="sida-(\d+)"', s[:m.start()])), default=self.page)
            bid = f"box-{self.count}"
            boxes.append(Box(bid, kind, title, page, excerpt(s[m.end():])))
            head = (f'<span class="box-kind">{label}</span>' if label else "") + \
                   (f'<span class="box-name">{title}</span>' if title else "")
            return (f'<div class="box box-{kind}" id="{bid}">'
                    + (f'<p class="box-title">{head}</p>' if head else ""))

        s = re.sub(r'<div class="(theorem|definition|example|note|framed)">\s*'
                   r"<p><strong>⟪(.*?)⟫</strong></p>", box, s, flags=re.S)
        self.page = max((int(p) for p in re.findall(r'id="sida-(\d+)"', s)), default=self.page)
        view.html, view.boxes = s, boxes
        return view


def excerpt(after: str, limit: int = 110) -> str:
    """The first paragraph of a box, cut at a word boundary outside maths."""
    m = re.search(r"<p>(.*?)</p>", after, re.S)
    if not m:
        return ""
    text = re.sub(r"<(?!/?span)[^>]+>", "", m.group(1)).strip()
    if len(text) <= limit:
        return text
    cut = 0
    for sp in re.finditer(r" ", text):
        before = text[:sp.start()]
        if sp.start() > limit:
            break
        if before.count("\\(") == before.count("\\)") and before.count("<span") == before.count("</span>"):
            cut = sp.start()
    return text[:cut] + " …" if cut else ""


def link_views(views: list[View]) -> None:
    """Point in-page links (#ref-9.18, #sida-12) at the view that holds the target: #f7~ref-9.18."""
    owner = {}
    for v in views:
        for i in re.findall(r'\sid="([^"]+)"', v.html):
            owner.setdefault(i, v.key)
    for v in views:
        v.html = re.sub(r'href="#([^"~]+)"',
                        lambda m: f'href="#{owner[m.group(1)]}~{m.group(1)}"' if m.group(1) in owner
                        else m.group(0), v.html)


def plain(tex: str) -> str:
    """Short LaTeX (a heading) as plain text."""
    s = re.sub(r"\\textcolor\{[^}]*\}", "", tex)
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    s = s.replace("\\ ", " ").replace("\\,", " ").replace("~", " ").replace("--", "–")
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s).replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


# --- Drawings and figures ---------------------------------------------------------------------

def render_drawings(out_dir: Path, dest: Path) -> list[str]:
    """TikZ redrawings (drawings/<id>.tex) as cropped PNGs in dest/<id>.png."""
    drawings = sorted((out_dir / "drawings").glob("*.tex"))
    if not drawings:
        return []
    tex = out_dir / "_site-drawings.tex"
    body = "\n".join(f"\\begin{{center}}\\input{{drawings/{d.name}}}\\end{{center}}\\newpage"
                     for d in drawings)
    tex.write_text(preamble().rstrip() + "\n\\pagestyle{empty}\n\\begin{document}\n" + body
                   + "\n\\end{document}\n", encoding="utf-8")
    result = compile_tex(tex)
    clean_aux(tex)
    if not result.ok:
        raise RuntimeError("drawings did not compile:\n" + "\n".join(result.errors))
    doc = pdfium.PdfDocument(result.pdf)
    for i, d in enumerate(drawings):
        img = doc[i].render(scale=4).to_pil().convert("RGB")
        bbox = ImageChops.difference(img, Image.new("RGB", img.size, "white")).getbbox()
        if bbox:
            pad = 24
            img = img.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                            min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad)))
        img.thumbnail((1400, 1400))
        img.save(dest / f"{d.stem}.png", optimize=True)
    doc.close()
    result.pdf.unlink(missing_ok=True)
    return [d.stem for d in drawings]


def inline_figures(page: str, fig_dir: Path) -> str:
    def data_uri(m: re.Match) -> str:
        f = fig_dir / m.group(1)
        if not f.exists():
            return m.group(0)
        return 'src="data:image/png;base64,' + base64.b64encode(f.read_bytes()).decode() + '"'
    return re.sub(r'src="figures/([^"]+)"', data_uri, page)


# --- Views ------------------------------------------------------------------------------------

def notes_tex(doc: Document) -> list[tuple[str, str]]:
    """(section title, LaTeX) per \\section of the notes, with page markers and theorem links."""
    bodies = add_navigation([p.body for p in doc.pages], list(range(1, len(doc.pages) + 1)))
    text = "".join(f"\n\n{PAGE_MARK.format(n)}\n\n{b}\n" for n, b in enumerate(bodies, 1))
    starts = [m.start() for m in re.finditer(r"^\\section\*?\{", text, re.M)]
    # whatever comes before the first section (at least the first page marker) belongs to it
    cuts = [0] + starts[1:] + [len(text)]
    sections = []
    for a, b in zip(cuts, cuts[1:]):
        chunk = text[a:b]
        m = re.search(r"\\section\*?\{", chunk)
        title = plain(braced(chunk, m.end() - 1)[0]) if m else "Anteckningar"
        sections.append((title, chunk))
    return sections


def satser_view(views: list[View], lang: str) -> View:
    parts = ['<h2>Satser och definitioner</h2>',
             '<p class="lede">Alla satser och definitioner i anteckningarna, i den ordning de '
             'kommer. Klicka för att läsa dem i sitt sammanhang.</p>']
    for v in views:
        rows = [b for b in v.boxes if b.kind in ("theorem", "definition")]
        if not rows:
            continue
        parts.append(f'<h3><a href="#{v.key}">{html.escape(v.title)}</a></h3><ul class="index">')
        for b in rows:
            label = BOX_KINDS[b.kind][0 if lang == "swedish" else 1]
            name = b.title or f'<span class="idx-excerpt">{b.excerpt}</span>'
            parts.append(f'<li class="idx-{b.kind}"><a href="#{v.key}~{b.id}">'
                         f'<span class="box-kind">{label}</span> <span class="idx-name">{name}</span>'
                         + (f'<span class="idx-page">s. {b.page}</span>' if b.page else "")
                         + "</a></li>")
        parts.append("</ul>")
    return View("satser", "Satser och definitioner", "\n".join(parts))


def exercises_view(items, converted: dict[str, str], page_view: dict[int, str]) -> View:
    parts = ['<h2>Övningar</h2>',
             f'<p class="lede">{len(items)} uppgifter ur anteckningarna: räknestugor, '
             'storgruppsövningar och tentauppgifter. Försök själv innan du öppnar lösningen.</p>',
             '<div class="ex-tools"><label class="switch"><input type="checkbox" id="ex-open"> '
             'Visa alla lösningar</label></div>']
    for i, ex in enumerate(items):
        where = page_view.get(ex.page)
        src = (f'<a class="ex-src" href="#{where}~sida-{ex.page}">sida {ex.page}</a>' if where
               else f'<span class="ex-src">sida {ex.page}</span>')
        parts.append(
            f'<article class="exercise" id="ex-{i + 1}"><header><h3>{html.escape(ex.heading)}</h3>{src}</header>'
            f'<div class="ex-q">{converted[f"exq{i}"]}</div>'
            + (f'<details class="ex-sol"><summary>Visa lösning</summary>'
               f'<div class="mj-defer">{converted[f"exs{i}"]}</div></details>' if ex.solution.strip()
               else '<p class="ex-none">Ingen lösning i anteckningarna.</p>')
            + "</article>")
    return View("ovningar", "Övningar", "\n".join(parts))


def flashcards_view(deck, converted: dict[str, str], page_view: dict[int, str], polish) -> View:
    cards = [{"f": polish.text(converted[f"cf{i}"]), "b": polish.text(converted[f"cb{i}"]), "p": page,
              "v": page_view.get(page, "")} for i, (_, _, page) in enumerate(deck)]
    data = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    body = f"""<h2>Flashcards</h2>
<p class="lede">{len(cards)} kort med definitioner och satser. Tänk ut svaret, vänd kortet och
markera om du kunde det. Det du markerar sparas bara i den här webbläsaren.</p>
<div class="deck" id="deck">
  <div class="deck-bar">
    <span class="deck-count" id="deck-count"></span>
    <label class="switch"><input type="checkbox" id="deck-unknown"> Bara kort jag inte kan</label>
    <button type="button" id="deck-shuffle">Blanda</button>
  </div>
  <div class="card" id="card" tabindex="0" aria-live="polite">
    <div class="card-face" id="card-front"></div>
    <div class="card-face card-back" id="card-back" hidden></div>
    <a class="card-src" id="card-src" href="#"></a>
  </div>
  <div class="deck-actions">
    <button type="button" id="deck-prev" aria-label="Föregående kort">←</button>
    <button type="button" class="primary" id="deck-flip">Vänd kortet</button>
    <button type="button" id="deck-no" hidden>Kunde inte</button>
    <button type="button" class="good" id="deck-yes" hidden>Kunde</button>
    <button type="button" id="deck-next" aria-label="Nästa kort">→</button>
  </div>
</div>
<script type="application/json" id="deck-data">{data}</script>"""
    return View("kort", "Flashcards", body)


def bevis_view(converted: str) -> View:
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', converted)
    toc = "".join(f'<li><a href="#bevis~{i}">{t}</a></li>' for i, t in heads)
    s = re.sub(r"<h2 ", "<h3 ", converted).replace("</h2>", "</h3>")
    s = re.sub(r"<p><span>\s*((?:Bevislistan|Anteckningarna)[^<]* sida \d+[^<]*)</span></p>",
               r'<p class="src-note">\1</p>', s)
    return View("bevis", "Bevislista", f"""<h2>Bevislista</h2>
<p class="lede">Satserna vars bevis ingår i kursen, med bevisen. Dölj bevisen för att öva: försök
bevisa satsen själv och klicka sedan på beviset för att se det.</p>
<div class="ex-tools"><label class="switch"><input type="checkbox" id="hide-proofs"> Dölj bevisen</label></div>
<ol class="bevis-toc">{toc}</ol>
<div class="bevis-body">{s}</div>""")


def home_view(title: str, notes: list[View], study: list[View], counts: dict[str, int]) -> View:
    desc = {"satser": f"{counts['satser']} satser och {counts['definitioner']} definitioner",
            "bevis": "bevisen som ingår i kursen",
            "ovningar": f"{counts['ovningar']} uppgifter med lösningar",
            "kort": f"{counts['kort']} kort att öva med",
            "formelblad": "de viktigaste formlerna samlade",
            "rattelser": "skrivfel i originalet som har rättats"}
    cards = "".join(f'<a class="dest" href="#{v.key}"><span class="dest-name">{html.escape(v.title)}</span>'
                    f'<span class="dest-desc">{desc.get(v.key, "")}</span></a>' for v in study)
    lectures = "".join(f'<li><a href="#{v.key}">{html.escape(v.title)}</a></li>' for v in notes)
    return View("hem", "Hem", f"""<div class="hero">
<p class="eyebrow">Handskrivna anteckningar, transkriberade</p>
<h1>{html.escape(title)}</h1>
<p class="lede">{counts['sidor']} sidor anteckningar som text och formler: sökbara, med länkar
mellan satser och med studiematerial byggt ur dem. Ett grönt
<span class="ink-rattat">†</span> markerar ett ställe där ett skrivfel i originalet har rättats.</p>
</div>
<nav class="dests" aria-label="Studiematerial">{cards}</nav>
<h2>Anteckningarna</h2>
<ol class="lectures">{lectures}</ol>""")


# --- Page -------------------------------------------------------------------------------------

def render_page(title: str, views: list[View]) -> str:
    """Page content (title, style, markup, scripts) without the <html>/<head>/<body> wrapper."""
    css = (TEMPLATES / "site.css").read_text(encoding="utf-8")
    js = (TEMPLATES / "site.js").read_text(encoding="utf-8")
    template = (TEMPLATES / "page.html").read_text(encoding="utf-8")
    notes = [v for v in views if v.group == "notes"]
    study = [v for v in views if v.group == "study" and v.key != "hem"]
    nav = ('<a href="#hem" data-view="hem">Hem</a>'
           + "".join(f'<a href="#{v.key}" data-view="{v.key}">{html.escape(v.title)}</a>' for v in study)
           + '<p class="nav-head">Anteckningar</p>'
           + "".join(f'<a href="#{v.key}" data-view="{v.key}">{html.escape(v.title)}</a>' for v in notes))
    sections = []
    for i, v in enumerate(views):
        pager = ""
        if v.group == "notes":
            k = notes.index(v)
            prev = f'<a href="#{notes[k - 1].key}">← {html.escape(notes[k - 1].title)}</a>' if k else "<span></span>"
            nxt = (f'<a href="#{notes[k + 1].key}">{html.escape(notes[k + 1].title)} →</a>'
                   if k + 1 < len(notes) else "<span></span>")
            pager = f'<nav class="pager" aria-label="Föreläsningar">{prev}{nxt}</nav>'
        sections.append(f'<section class="view" id="view-{v.key}" data-key="{v.key}" '
                        f'data-group="{v.group}" data-title="{html.escape(v.title)}" hidden>'
                        f"{v.html}{pager}</section>")
    return (template.replace("{{TITLE}}", html.escape(title)).replace("{{CSS}}", css)
            .replace("{{NAV}}", nav).replace("{{VIEWS}}", "\n".join(sections)).replace("{{JS}}", js))


def full_document(content: str) -> str:
    return ('<!doctype html>\n<html lang="sv">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"</head>\n<body>\n{content}\n</body>\n</html>\n")


def write_index(site_dir: Path) -> Path:
    docs = []
    for meta in sorted(site_dir.glob("*/meta.json")):
        docs.append((meta.parent.name, json.loads(meta.read_text(encoding="utf-8"))))
    items = "".join(f'<li><a href="{name}/index.html">{html.escape(m["title"])}</a>'
                    f'<span>{m["pages"]} sidor · byggd {m["built"]}</span></li>' for name, m in docs)
    css = (TEMPLATES / "site.css").read_text(encoding="utf-8")
    content = (f"<title>Anteckningar</title>\n<style>{css}</style>\n"
               f'<main class="index-page"><h1>Anteckningar</h1><ul class="doc-list">{items}</ul></main>')
    out = site_dir / "index.html"
    out.write_text(full_document(content), encoding="utf-8")
    return out


def build_site(out_dir: Path, site_dir: Path, title: str) -> tuple[Path, Path]:
    doc = load(out_dir)
    lang = doc.language
    dest = site_dir / out_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "figures").mkdir(parents=True)

    # sources: notes per section, study material
    sections = notes_tex(doc)
    segments = {f"f{i + 1}": tex for i, (_, tex) in enumerate(sections)}
    segments["bevis"] = bevislista_body(out_dir, doc)   # also copies borrowed figures in
    items = exercises(doc)
    for i, ex in enumerate(items):
        segments[f"exq{i}"] = ex.question
        segments[f"exs{i}"] = ex.solution
    deck = load_deck(out_dir, doc)
    for i, (front, back, _) in enumerate(deck):
        segments[f"cf{i}"] = front
        segments[f"cb{i}"] = back
    extras = []
    for f in sorted((out_dir / "extras").glob("*.tex")):
        text = f.read_text(encoding="utf-8")
        m = re.match(r"%\s*title:\s*(.*)\n", text)
        name = re.sub(r"\s*--.*$", "", m.group(1)) if m else f.stem
        key = re.sub(r"[^a-z0-9]+", "-", f.stem.lower())
        extras.append((key, name))
        segments[f"x-{key}"] = text
    converted = pandoc(segments)

    polish = Polisher(lang)
    notes = [polish(View(f"f{i + 1}", t, converted[f"f{i + 1}"], "notes")) for i, (t, _) in enumerate(sections)]
    page_view = {}
    for v in notes:
        for p in re.findall(r'id="sida-(\d+)"', v.html):
            page_view[int(p)] = v.key
    bevis = polish(bevis_view(converted["bevis"]))
    ex_view = polish(exercises_view(items, converted, page_view))
    kort = polish(flashcards_view(deck, converted, page_view, polish))
    extra_views = [polish(View(k, n, f"<h2>{html.escape(n)}</h2>\n" + converted[f"x-{k}"])) for k, n in extras]
    satser = satser_view(notes, lang)
    counts = {"sidor": len(doc.pages), "ovningar": len(items), "kort": len(deck),
              "satser": sum(b.kind == "theorem" for v in notes for b in v.boxes),
              "definitioner": sum(b.kind == "definition" for v in notes for b in v.boxes)}
    study = [satser, bevis, ex_view, kort] + extra_views
    views = [home_view(title, notes, study, counts)] + study + notes
    link_views(views)

    # figures: crops of the handwriting, then the TikZ redrawings on top
    for f in (out_dir / "figures").glob("*.png"):
        shutil.copy(f, dest / "figures" / f.name)
    render_drawings(out_dir, dest / "figures")

    content = render_page(title, views)
    index = dest / "index.html"
    index.write_text(full_document(content), encoding="utf-8")
    artifact = dest / "artifact.html"
    artifact.write_text(inline_figures(content, dest / "figures"), encoding="utf-8")
    (dest / "meta.json").write_text(json.dumps({"title": title, "pages": len(doc.pages),
                                                "built": date.today().isoformat()},
                                               ensure_ascii=False), encoding="utf-8")
    write_index(site_dir)
    return index, artifact
