"""Study material generated from a transcribed document.

    bevislista   theorems the notes mark as part of the exam proof list, with their proofs
                 (or, with "källa: <name>" in extras/bevislista.txt, those of a separate proof document)
    ovningar     exercises and exam questions without solutions (and a version with solutions)
    flashcards   one card per definition/theorem: Anki import file + printable PDF
    hand-written extras/<name>.tex bodies (formula sheet, errata, ...) are compiled as well

Each PDF is written next to the main document (output/<name>/<name>-<extra>.pdf) so figures and
drawings resolve the same way.
"""

from __future__ import annotations

import html
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.assemble import LANGUAGES, Page, preamble
from app.pipeline.compile import CompileResult, clean_aux, compile_tex
from app.pipeline.run import load_transcribed

# Text that ends a theorem's "neighbourhood": everything up to here belongs with the theorem
# (its proof, lemmas, continued proofs across a page break).
STOP = re.compile(r"\\begin\{(?:theorem|definition)\}|\\section\*?\{|\\subsection\*?\{|\\noindent\\rule")
NEXT_THEOREM = re.compile(r"\\begin\{theorem\}")
PAGE_MARK = re.compile(r"\n?%%PAGE (\d+)%%\n?")
THEOREM = re.compile(r"\\begin\{theorem\}(?:\[(?P<title>(?:[^\[\]]|\[[^\]]*\])*)\])?")
EXERCISE_START = re.compile(
    r"^\s*(?:\\fbox\{|\\subsection\*?\{(?:Tenta|Övning|F\s?\d|F\d|20\d\d|Uppgift|Häftet|Tentauppgift)"
    r"|\\textbf\{Övning|Sid(?:a)?\s+\d)")


@dataclass
class Document:
    pages: list[Page]
    text: str           # all page bodies joined, with %%PAGE n%% markers
    language: str

    def page_at(self, pos: int) -> int:
        marks = [(m.start(), int(m.group(1))) for m in PAGE_MARK.finditer(self.text)]
        return max((n for start, n in marks if start <= pos), default=1)


def load(out_dir: Path) -> Document:
    pages = load_transcribed(out_dir)
    if not pages:
        raise ValueError(f"no transcribed pages in {out_dir / 'pages'}")
    text = "".join(f"\n%%PAGE {n}%%\n{p.body}\n" for n, p in enumerate(pages, 1))
    lang = pages[0].language if pages[0].language in LANGUAGES else "english"
    return Document(pages, text, lang)


def braced(text: str, start: int) -> tuple[str, int]:
    """Content of the {...} group opening at text[start], and the index after it."""
    depth = 0
    for i in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start + 1: i], i + 1
    return text[start + 1:], len(text)


def command_arg(text: str, command: str) -> tuple[str, int] | None:
    """If text (after leading space) starts with \\command{...}: (argument, end index)."""
    m = re.match(r"\s*\\" + command + r"\{", text)
    return braced(text, m.end() - 1) if m else None


def strip_marks(text: str) -> str:
    return PAGE_MARK.sub("\n", text).strip()


def write_pdf(out_dir: Path, suffix: str, title: str, body: str, lang: str,
              toc: bool = False) -> CompileResult:
    tex = out_dir / f"{out_dir.name}-{suffix}.tex"
    head = preamble().rstrip() + f"\n\n\\begin{{document}}\n\\selectlanguage{{{lang}}}\n"
    head += f"\\section*{{{title}}}\n"
    if toc:
        head += "\\tableofcontents\n\\newpage\n"
    tex.write_text(head + body + "\n\\end{document}\n", encoding="utf-8")
    result = compile_tex(tex)
    clean_aux(tex)
    return result


# --- Bevislista -------------------------------------------------------------------------------

def theorem_blocks(doc: Document, stop_at: re.Pattern = STOP) -> list[tuple[int, str, str]]:
    """(page, title, text from the theorem up to the next stop) for every theorem."""
    blocks = []
    for m in THEOREM.finditer(doc.text):
        end = doc.text.find("\\end{theorem}", m.end())
        stop = stop_at.search(doc.text, end)
        chunk = doc.text[m.start(): stop.start() if stop else len(doc.text)]
        blocks.append((doc.page_at(m.start()), (m.group("title") or "").strip(), chunk))
    return blocks


def default_selection(doc: Document) -> list[str]:
    """Theorems whose text says they are on the proof list ('bevislista'), not 'inte/ej'."""
    lines = []
    for page, title, chunk in theorem_blocks(doc):
        theorem = chunk[: chunk.find("\\end{theorem}")]
        if re.search(r"bevislist", theorem, re.I) and not re.search(r"(inte|ej)\W+\S*\W*bevislist", theorem, re.I):
            lines.append(f"p{page}: {title}")
    return lines


def bevislista(doc: Document, selection: list[str], source: str = "Anteckningarna") -> str:
    """One section per selected theorem with its proof. A dedicated proof document (source) has
    nothing but theorems and proofs, so there each block runs on to the next theorem."""
    blocks = theorem_blocks(doc) if source == "Anteckningarna" else theorem_blocks(doc, NEXT_THEOREM)
    parts = []
    for line in selection:
        m = re.match(r"p(\d+):\s*(.*?)(?:\s*\|\s*(.*))?$", line.strip())
        if not m:
            continue
        page, title, comment = int(m.group(1)), m.group(2), m.group(3)
        found = [b for b in blocks if b[0] == page and title in b[1]]
        if not found:
            raise ValueError(f"bevislista: no theorem '{title}' on page {page}")
        _, full_title, chunk = found[0]
        heading = re.sub(r"\s*\(.*?\)\s*$", "", full_title) or f"Sats på sida {page}"
        parts.append(f"\\section{{{heading}}}\n{{\\small\\color{{gray}} {source} sida {page}"
                     + (f" -- {comment}" if comment else "") + "}\n\n" + strip_marks(chunk))
    return "\n\n\\newpage\n".join(parts)


def borrow_figures(source_dir: Path, out_dir: Path, body: str) -> str:
    """Copy the source document's figures and drawings next to ours, with its name as prefix."""
    prefix = source_dir.name + "-"
    for sub, ext in (("figures", "png"), ("drawings", "tex")):
        for f in (source_dir / sub).glob(f"*.{ext}"):
            (out_dir / sub).mkdir(exist_ok=True)
            shutil.copy(f, out_dir / sub / (prefix + f.name))
    return re.sub(r"(\\notefigure(?:\[[^\]]*\])?\{)", r"\1" + prefix, body)


# --- Övningar ---------------------------------------------------------------------------------

@dataclass
class Exercise:
    page: int
    heading: str
    question: str
    solution: str


def balanced(tex: str) -> bool:
    return len(re.findall(r"\\begin\{", tex)) == len(re.findall(r"\\end\{", tex))


def exercise_bounds(text: str) -> list[int]:
    """Split points: separators, headings, and exercise numbers at the start of a line (a new
    exercise that follows the previous one directly, e.g. across a page break)."""
    points = {m.start() for m in re.finditer(
        r"\\noindent\\rule\{\\linewidth\}\{0\.4pt\}|\\section\*?\{|\\subsection\*?\{", text)}
    for m in re.finditer(r"^(?:\\fbox\{\d|Sid(?:a)?\s+\d)", text, re.M):
        line_start = m.start()
        prev = text.rfind("\n", 0, line_start - 1)
        if text[prev + 1: line_start].lstrip().startswith("\\begin{minipage}"):
            line_start = prev + 1  # keep a minipage that opens with the exercise together
        points.add(line_start)
    points = sorted(points) + [len(text)]
    # Drop split points that would cut an environment in half.
    kept = [points[0]]
    for p in points[1:]:
        if p == len(text) or balanced(text[kept[-1]:p]):
            kept.append(p)
    return kept


def plain_heading(tex: str) -> str:
    tex = re.sub(r"\\textcircled\{([^{}]*)\}", r"(\1)", tex)
    tex = re.sub(r"\\textcolor\{[^}]*\}", "", tex)
    tex = re.sub(r"\\(?:fbox|textbf|emph)", "", tex)
    return re.sub(r"\s+", " ", tex.replace("{", "").replace("}", "")).strip()


def exercises(doc: Document) -> list[Exercise]:
    bounds = exercise_bounds(doc.text)
    context = ""
    found = []
    for a, b in zip(bounds, bounds[1:]):
        chunk = doc.text[a:b]
        chunk = re.sub(r"^\\noindent\\rule\{\\linewidth\}\{0\.4pt\}", "", chunk)
        sec = command_arg(chunk, r"section\*?")
        if sec:
            context, end = plain_heading(sec[0]), sec[1]
            chunk = chunk[end:]
        plain = strip_marks(chunk)
        lead = re.match(r"\s*\\begin\{minipage\}(?:\[[^\]]*\])?\{[^}]*\}\s*", plain)
        probe = plain[lead.end():] if lead else plain   # exercise text may open inside a minipage
        if not EXERCISE_START.match(probe):
            continue
        heading = ""
        sub = command_arg(plain, r"subsection\*?")
        if sub:
            heading, plain = sub[0], plain[sub[1]:].lstrip()
        else:
            box = command_arg(probe, "fbox")
            sida = re.match(r"(Sid(?:a)?\s*\d+)\.?\s*(?:\\textcircled\{(\w+)\})?", probe)
            if box:
                heading = f"Uppgift {box[0]}" if box[0][:1].isdigit() else plain_heading(box[0]).rstrip(":")
            elif sida:
                heading = sida.group(1) + (f", uppgift {sida.group(2)}" if sida.group(2) else "")
            elif plain.startswith("\\textbf{Övning"):
                heading = "Övning"
        split = re.search(r"\\textbf\{Lösning", plain)
        if split:
            question, solution = plain[: split.start()], plain[split.start():]
        else:  # no solution label: the question ends at the first blank line, display or figure
            ends = sorted(m.start() for m in re.finditer(
                r"\n\s*\n|\\\[|\\begin\{align|\\notefigure", plain))
            ends += sorted(m.end() for m in re.finditer(r"\\end\{minipage\}\s*", plain))
            cut = min((e for e in ends if e > 0 and balanced(plain[:e])), default=len(plain))
            question, solution = plain[:cut], plain[cut:]
        question = re.sub(r"\\hfill\s*\$\\longrightarrow\$\s*$", "", question.strip())
        heading = plain_heading(heading) if heading else "Övning"
        found.append(Exercise(doc.page_at(a), heading + (f" ({context})" if context else ""),
                              question.strip(), solution.strip()))
    return found


def ovningar(items: list[Exercise], with_solutions: bool) -> str:
    parts = []
    for i, ex in enumerate(items, 1):
        head = f"\\subsection*{{{i}. {ex.heading}}}\n{{\\small\\color{{gray}} Anteckningarna sida {ex.page}}}\n\n"
        body = ex.question
        if not with_solutions:  # sketches next to a question are usually part of the answer
            body = re.sub(r"\\notefigure(?:\[[^\]]*\])?\{[^}]*\}\{[^}]*\}", "", body)
        if with_solutions:
            body += "\n\n" + (ex.solution or "\\emph{(Ingen lösning i anteckningarna.)}")
        else:
            body += "\n\n\\vspace{2.5cm}"
        parts.append(head + body)
    return "\n\n\\noindent\\rule{\\linewidth}{0.4pt}\n\n".join(parts)


# --- Flashcards -------------------------------------------------------------------------------

ENV = re.compile(r"\\begin\{(theorem|definition)\}(?:\[(?P<title>(?:[^\[\]]|\[[^\]]*\])*)\])?"
                 r"(?P<body>.*?)\\end\{\1\}", re.S)


def cards(doc: Document) -> list[tuple[str, str, int]]:
    """(front, back, page) per definition/theorem, skipping a final 'Repetition' section."""
    rep = re.search(r"\\section\{Repetition\}", doc.text)
    text = doc.text[: rep.start()] if rep else doc.text
    out = []
    for m in ENV.finditer(text):
        kind, title, body = m.group(1), (m.group("title") or "").strip(), strip_marks(m.group("body"))
        body = re.sub(r"\\notefigure(?:\[[^\]]*\])?\{[^}]*\}\{[^}]*\}", "", body).strip()
        body = re.sub(r"^\\hfill\s*\\textcolor\{[^}]*\}\{[^}]*\}\s*", "", body).strip()  # "Bevislistan" tags
        if not body:
            continue
        if kind == "definition":
            terms = re.findall(r"\\emph\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", body)
            symbol = re.search(r"\$([^$=]+?)\s*(?:=|\$)", body)  # "$\operatorname{Log} z = ...$"
            front = "Definiera: " + (", ".join(terms[:2]) if terms else title if title else
                                     f"${symbol.group(1).strip()}$" if symbol else
                                     f"definitionen på sida {doc.page_at(m.start())}")
        else:
            front = f"Vad säger {title}?" if title and title[0].isalpha() else \
                    f"Formulera satsen {title or ''} (sida {doc.page_at(m.start())})".replace("  ", " ")
        out.append((front, body, doc.page_at(m.start())))
    return out


def flashcards_pdf(items: list[tuple[str, str, int]]) -> str:
    return "\n".join(
        f"\\begin{{tcolorbox}}[enhanced,breakable,colback=white,colframe=blue!40!black,"
        f"fonttitle=\\bfseries,title={{{i}. {front}}}]\n{{\\small\\color{{gray}} sida {page}}}\\par\n"
        f"{back}\n\\end{{tcolorbox}}"
        for i, (front, back, page) in enumerate(items, 1))


def to_anki(tex: str) -> str:
    """Convert a LaTeX snippet to Anki HTML with MathJax (\\( \\) and \\[ \\])."""
    s = tex
    for _ in range(3):  # nested colour / emphasis
        s = re.sub(r"\\textcolor\{[^}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", s)
        s = re.sub(r"\\unsure\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", s)
        s = re.sub(r"\\rattat\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}"
                   r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}", r"\1", s)  # keep the correction
    s = re.sub(r"\\begin\{(align\*?|aligned)\}", r"\\[\\begin{aligned}", s)
    s = re.sub(r"\\end\{(align\*?|aligned)\}", r"\\end{aligned}\\]", s)
    s = re.sub(r"\$\$(.+?)\$\$", r"\\[\1\\]", s, flags=re.S)
    s = re.sub(r"(?<!\\)\$(.+?)(?<!\\)\$", r"\\(\1\\)", s, flags=re.S)
    # Text-only conversions must not touch the maths, so set the formulas aside first.
    maths: list[str] = []
    s = re.sub(r"\\\[.*?\\\]|\\\(.*?\\\)",
               lambda m: maths.append(m.group(0)) or f"\x00{len(maths) - 1}\x00", s, flags=re.S)
    s = re.sub(r"\\(?:begin|end)\{minipage\}(?:\[[^\]]*\])?(?:\{[^}]*\})?|\\vrule", " ", s)
    s = re.sub(r"\\begin\{(?:enumerate|itemize)\}(?:\[[^\]]*\])?", "<ul>", s)
    s = re.sub(r"\\end\{(?:enumerate|itemize)\}", "</ul>", s)
    s = re.sub(r"\\item\s*", "<li>", s)
    s = re.sub(r"\\emph\{([^{}]*)\}", r"<i>\1</i>", s)
    s = re.sub(r"\\textbf\{([^{}]*)\}", r"<b>\1</b>", s)
    s = re.sub(r"\\(?:hfill|noindent|par|medskip|quad|qquad)\b", " ", s)
    s = s.replace("\\\\", "<br>").replace("~", " ").replace("\\ ", " ")
    s = re.sub(r"\n\s*\n", "<br><br>", s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: maths[int(m.group(1))], s)
    return re.sub(r"\s+", " ", s).replace("\t", " ").strip()


def anki_file(items: list[tuple[str, str, int]]) -> str:
    rows = ["#separator:tab", "#html:true", "#columns:Front\tBack"]
    rows += [f"{to_anki(front)}\t{to_anki(back)}" for front, back, _ in items]
    return "\n".join(rows) + "\n"


# --- Driver -----------------------------------------------------------------------------------

def build_extras(out_dir: Path, title: str) -> dict[str, CompileResult | Path]:
    doc = load(out_dir)
    extras_dir = out_dir / "extras"
    extras_dir.mkdir(exist_ok=True)
    results: dict[str, CompileResult | Path] = {}

    sel_file = extras_dir / "bevislista.txt"
    if not sel_file.exists():
        sel_file.write_text("# One theorem per line: p<page>: <part of its title> [| comment]\n"
                            + "\n".join(default_selection(doc)) + "\n", encoding="utf-8")
    selection = [l for l in sel_file.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
    source = next((l.split(":", 1)[1].strip() for l in selection if l.startswith("källa:")), None)
    if source:  # "källa: <name>": take the proofs from output/<name>/ instead of these notes
        body = bevislista(load(out_dir.parent / source), selection, f"Bevislistan ({source})")
        body = borrow_figures(out_dir.parent / source, out_dir, body)
    else:
        body = bevislista(doc, selection)
    results["bevislista"] = write_pdf(out_dir, "bevislista", f"Bevislista -- {title}",
                                      body, doc.language, toc=True)

    items = exercises(doc)
    results["ovningar"] = write_pdf(out_dir, "ovningar", f"Övningar -- {title}",
                                    ovningar(items, False), doc.language)
    results["ovningar-losningar"] = write_pdf(out_dir, "ovningar-losningar",
                                              f"Övningar med lösningar -- {title}",
                                              ovningar(items, True), doc.language)

    deck = cards(doc)
    fronts = extras_dir / "flashcards.txt"   # "p40: <automatic front> => <better front>"
    if fronts.exists():
        overrides = {}
        for line in fronts.read_text(encoding="utf-8").splitlines():
            m = re.match(r"p(\d+):\s*(.*?)\s*=>\s*(.*)$", line)
            if m:
                overrides[(int(m.group(1)), m.group(2))] = m.group(3)
        deck = [(overrides.get((page, front), front), back, page) for front, back, page in deck]
    results["flashcards"] = write_pdf(out_dir, "flashcards", f"Flashcards -- {title}",
                                      flashcards_pdf(deck), doc.language)
    anki = out_dir / f"{out_dir.name}-anki.txt"
    anki.write_text(anki_file(deck), encoding="utf-8")
    results["anki"] = anki

    for body in sorted(extras_dir.glob("*.tex")):  # hand-written: formelblad, errata, ...
        text = body.read_text(encoding="utf-8")
        m = re.match(r"%\s*title:\s*(.*)\n", text)
        results[body.stem] = write_pdf(out_dir, body.stem, m.group(1) if m else body.stem,
                                       text, doc.language)
    return results
