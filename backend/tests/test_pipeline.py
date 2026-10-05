"""Pipeline tests: prepare -> (page files written by hand here) -> build. Needs LaTeX installed."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.pipeline.assemble import Figure, Page, clean_body, find_unsure, parse_page
from app.pipeline.preprocess import parse_page_range
from app.pipeline.run import body_relative_errors, build, prefix_figures, prepare_pages


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    img = Image.new("RGB", (800, 1100), "white")
    ImageDraw.Draw(img).rectangle((100, 100, 400, 400), outline="black", width=5)
    path = tmp_path / "page.jpg"
    img.save(path)
    return path


@pytest.fixture
def lecture_pdf(tmp_path: Path) -> Path:
    """4-page PDF: pages 1, 2 and 4 have writing, page 3 is blank."""
    pages = []
    for n in range(4):
        img = Image.new("RGB", (850, 1100), "white")
        if n != 2:
            ImageDraw.Draw(img).text((100, 100 + 50 * n), f"Page {n + 1}: x^2 + y^2 = r^2",
                                     fill="black", font_size=40)
        pages.append(img)
    path = tmp_path / "lecture.pdf"
    pages[0].save(path, save_all=True, append_images=pages[1:])
    return path


def write_page(out_dir: Path, n: int, text: str) -> None:
    (out_dir / "pages" / f"p{n}.tex").write_text(text, encoding="utf-8")


def test_prepare_creates_images_and_grids(tmp_path, photo):
    pages = prepare_pages([photo, photo], tmp_path / "notes").pages
    assert [p.number for p in pages] == [1, 2]
    assert all(p.image.exists() and p.grid.exists() for p in pages)
    assert not pages[0].transcription.exists()


def test_build_reports_missing_pages(tmp_path, photo):
    out = tmp_path / "notes"
    prepare_pages([photo, photo], out)
    write_page(out, 1, "Hello")
    result = build(out)
    assert not result.ok and result.missing == [2]


def test_full_build_with_figure_and_swedish(tmp_path, photo):
    out = tmp_path / "notes"
    prepare_pages([photo, photo], out)
    write_page(out, 1, "% language: swedish\n% figure: fig1 0.1 0.1 0.5 0.4\n"
                       r"\section{Kraft}$\vb{F} = \unsure{m}\vb{a}$ \notefigure{fig1}{Kraftdiagram}")
    write_page(out, 2, r"\begin{example}\ce{H2O}, \SI{3}{\metre}\end{example}")
    result = build(out, title="Fysik")

    assert result.ok, (result.page_errors, result.errors)
    assert result.pdf.exists()
    assert (out / "figures" / "p1-fig1.png").exists()
    tex = result.tex.read_text()
    assert r"\notefigure[0.44]{p1-fig1}{Kraftdiagram}" in tex
    assert r"\selectlanguage{swedish}" in tex
    assert result.uncertain == {1: ["m"]}


def test_errors_point_at_line_in_page_file(tmp_path, photo):
    out = tmp_path / "notes"
    prepare_pages([photo, photo], out)
    write_page(out, 1, "Fine page")
    # Header takes lines 1-2, the typo is on line 6 of p2.tex.
    write_page(out, 2, "% language: english\n\nLine one\n\nLine three\n$x^2 = \\fracc{1}{2}$\n")
    result = build(out)

    assert not result.ok
    assert list(result.page_errors) == [2]
    assert "line 6" in "\n".join(result.page_errors[2])
    assert not list(out.glob("_check-*"))

    write_page(out, 2, "Line one\n\nLine three\n$x^2 = \\frac{1}{2}$\n")
    assert build(out).ok


def test_parse_page_header():
    page = parse_page("% language: Swedish\n% figure: fig2 0.1 0.2 0.3 0.4\n\nBody\n% a comment")
    assert page.language == "swedish"
    assert page.figures == [Figure("fig2", [0.1, 0.2, 0.3, 0.4])]
    assert page.body == "Body\n% a comment"
    assert page.first_line == 4


def test_parse_page_rejects_bad_figure_line():
    with pytest.raises(ValueError):
        parse_page("% figure: fig1 0.1 0.2\nBody")


def test_find_unsure_handles_nested_braces():
    assert find_unsure(r"a \unsure{\frac{1}{x}} b \unsure{word}") == [r"\frac{1}{x}", "word"]


def test_clean_body_strips_preamble_and_fences():
    body = "```latex\n\\documentclass{article}\n\\begin{document}\nHello $x$\n\\end{document}\n```"
    assert clean_body(body) == "Hello $x$"


def test_prefix_figures():
    page = Page(body=r"a \notefigure{fig1}{} b \notefigure{fig2}{c}",
                figures=[Figure("fig1", [0, 0, 1, 1]), Figure("fig2", [0, 0, 1, 1])])
    prefix_figures(page, "p3-")
    assert [f.id for f in page.figures] == ["p3-fig1", "p3-fig2"]
    assert r"\notefigure[1.00]{p3-fig1}{}" in page.body and r"\notefigure[1.00]{p3-fig2}{c}" in page.body


def test_body_relative_errors():
    errs = body_relative_errors(["./doc.tex:105: Missing $ inserted.\nl.105 $x"], offset=100)
    assert errs == ["line 4: Missing $ inserted.\nline 4 $x"]


def test_pdf_is_split_and_blank_pages_skipped(tmp_path, lecture_pdf):
    result = prepare_pages([lecture_pdf], tmp_path / "notes")
    assert [p.source for p in result.pages] == ["lecture.pdf p1", "lecture.pdf p2", "lecture.pdf p4"]
    assert result.blank == ["lecture.pdf p3"]
    assert all(p.image.exists() for p in result.pages)
    with Image.open(result.pages[0].image) as img:
        assert max(img.size) == 2400


def test_pdf_page_range_and_keep_blank(tmp_path, lecture_pdf):
    result = prepare_pages([lecture_pdf], tmp_path / "notes", page_range="2-3", keep_blank=True)
    assert [p.source for p in result.pages] == ["lecture.pdf p2", "lecture.pdf p3"]


def test_mixed_pdf_and_photo(tmp_path, lecture_pdf, photo):
    result = prepare_pages([lecture_pdf, photo], tmp_path / "notes", page_range="1")
    assert [p.source for p in result.pages] == ["lecture.pdf p1", "page.jpg"]


def test_rerun_moves_transcriptions_with_their_page(tmp_path, lecture_pdf):
    out = tmp_path / "notes"
    prepare_pages([lecture_pdf], out)               # p1=pdf p1, p2=pdf p2, p3=pdf p4
    for n, label in ((1, "pdf p1"), (2, "pdf p2"), (3, "pdf p4")):
        write_page(out, n, label)
    result = prepare_pages([lecture_pdf], out, page_range="1,4")  # p1=pdf p1, p2=pdf p4
    pages = out / "pages"
    assert (pages / "p1.tex").read_text() == "pdf p1"
    assert (pages / "p2.tex").read_text() == "pdf p4"  # moved from p3 to p2
    assert not (pages / "p3.tex").exists()
    assert (pages / "p2.stale.tex").read_text() == "pdf p2"  # its page is no longer included
    assert result.stale == ["p2.tex (lecture.pdf p2)"]


def test_parse_page_range():
    assert parse_page_range(None, 3) == [0, 1, 2]
    assert parse_page_range("1-2, 5", 10) == [0, 1, 4]
    assert parse_page_range("3-99", 4) == [2, 3]
    with pytest.raises(ValueError):
        parse_page_range("two", 4)


def test_partial_build_stops_at_first_missing_page(tmp_path, photo):
    out = tmp_path / "notes"
    prepare_pages([photo, photo, photo], out)
    write_page(out, 1, "One")
    write_page(out, 3, "Three")
    result = build(out, partial=True)
    assert result.ok
    assert "One" in result.tex.read_text() and "Three" not in result.tex.read_text()


def test_navigation_links_references_to_numbered_theorems():
    from app.pipeline.navigation import add_navigation
    bodies = [r"\begin{theorem}[Rouchés sats (Sats 9.18)]X\end{theorem} se Prop 7.25b",
              r"enligt \text{sats 9.18} och Kor 1.1 \begin{theorem}[2.17]Y\end{theorem}"]
    out = add_navigation(bodies, [1, 2])
    assert r"\hypertarget{ref-9.18}{}" in out[0]
    assert r"\theoremindex{Rouchés sats (Sats 9.18)}" in out[0]
    assert "[Rouchés sats (Sats 9.18)]" in out[0]           # title itself is not turned into a link
    assert r"\hyperlink{ref-9.18}{sats 9.18}" in out[1]
    assert "Kor 1.1" in out[1] and "ref-1.1" not in out[1]   # no theorem with that number
    assert r"\theoremindex{Sats 2.17}" in out[1]


def test_exercises_split_question_and_solution(tmp_path, photo):
    from app.pipeline.extras import exercises, load
    out = tmp_path / "notes"
    prepare_pages([photo, photo], out)
    write_page(out, 1, "\\section{Räknestuga 1/1}\n\\fbox{1.2} \\quad Beräkna $x$.\n\n"
                       "\\textbf{Lösning:} $x = 1$\n\n\\noindent\\rule{\\linewidth}{0.4pt}\n\n"
                       "\\fbox{1.3} \\quad Visa $y$.\n\\[ y = 2 \\]")
    write_page(out, 2, "\\fbox{1.4} \\quad Hitta $z$ (forts. från förra sidan).\n\n\\textbf{Lösning:} $z$")
    ex = exercises(load(out))
    assert [e.heading for e in ex] == ["Uppgift 1.2 (Räknestuga 1/1)", "Uppgift 1.3 (Räknestuga 1/1)",
                                       "Uppgift 1.4 (Räknestuga 1/1)"]
    assert ex[0].question.endswith("Beräkna $x$.") and ex[0].solution.startswith("\\textbf{Lösning")
    assert ex[1].question.endswith("Visa $y$.") and "y = 2" in ex[1].solution   # no label: cut at display
    assert ex[2].page == 2


def test_anki_conversion_keeps_maths_intact():
    from app.pipeline.extras import to_anki
    out = to_anki(r"Om \emph{holomorf}: $f' = 0$ \begin{align*} a &= b \\ c &= d \end{align*}")
    assert "<i>holomorf</i>" in out and r"\(f' = 0\)" in out
    assert r"\[\begin{aligned} a &= b \\ c &= d \end{aligned}\]" in out


def test_anki_keeps_corrections_not_originals():
    from app.pipeline.extras import to_anki
    out = to_anki(r"$B = \rattat{-\frac{1}{2}}{\frac{1}{2}}$ och \rattat{Parsevals}{Pascals} formel")
    assert r"B = -\frac{1}{2}" in out and "Parsevals formel" in out
    assert "rattat" not in out and "Pascals" not in out


def test_review_plain_text():
    from app.pipeline.review import as_text, to_plain
    assert to_plain(r"= \overline{z\bar{w}}") == "= (zw̄)̄"
    assert to_plain(r"$w\bar z = \overline{z\bar w}$") == "wz̄ = (zw̄)̄"
    assert to_plain(r"svaret är $\pi\min(a, b)$, ''komplement''") == 'svaret är πmin(a, b), "komplement"'
    assert as_text("hemsidan") == "hemsidan" and as_text(r"\varphi") == r"$\varphi$"


def test_review_keeps_existing_answers(tmp_path):
    from app.pipeline.review import read_answers
    txt = tmp_path / "x-granskning.txt"
    txt.write_text("1. Sida 3. Läst som: φ\n   Svar: ok\n\n2. Sida 9. Läst som: hemsidan\n   Svar: \n")
    assert read_answers(txt) == {(3, "φ"): "ok"}


def test_bevislista_from_separate_proof_document(tmp_path):
    from app.pipeline.extras import Document, bevislista, borrow_figures
    text = ("\n%%PAGE 1%%\n\\begin{theorem}[Residysatsen]X\\end{theorem}\n\\noindent\\rule{1pt}{1pt}\n"
            "\\begin{definition}D\\end{definition}\n%%PAGE 2%%\n\\begin{proof}P \\notefigure[0.5]{p2-fig1}{}"
            "\\end{proof}\n%%PAGE 3%%\n\\begin{theorem}[Rouchés sats]Y\\end{theorem}")
    doc = Document([], text, "swedish")
    body = bevislista(doc, ["källa: bevis", "p1: Residysatsen"], "Bevislistan (bevis)")
    assert "\\begin{proof}P" in body and "Rouchés" not in body   # runs past the rule to the proof
    assert "Bevislistan (bevis) sida 1" in body
    (tmp_path / "bevis" / "figures").mkdir(parents=True)
    (tmp_path / "bevis" / "figures" / "p2-fig1.png").write_bytes(b"png")
    (tmp_path / "notes").mkdir()
    body = borrow_figures(tmp_path / "bevis", tmp_path / "notes", body)
    assert "\\notefigure[0.5]{bevis-p2-fig1}{}" in body
    assert (tmp_path / "notes" / "figures" / "bevis-p2-fig1.png").exists()
