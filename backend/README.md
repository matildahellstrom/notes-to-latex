# Notes → LaTeX

Turns handwritten maths and science notes (PDFs, scans or photos) into a `.tex` file and a PDF. Claude Code does the transcription on your Claude subscription, so there is no API key and no per-page cost.

## Setup (once)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

LaTeX: needs `latexmk` + `xelatex` (included in MacTeX / TeX Live), or Tectonic.

## Use

1. Put your notes in `notes-in/`: PDFs (each page becomes a page of notes) or photos. Several files are taken in name order.
2. In Claude Code, in this project, type:

   ```
   /transcribe
   ```

   or with options:

   ```
   /transcribe notes-in/fysik-f3.pdf --pages 1-4 --title "Fysik 1, föreläsning 3"
   ```

3. The result is in `output/<name>/`:

| File | What it is |
|---|---|
| `<name>.pdf` | the compiled notes; uncertain readings are highlighted yellow |
| `<name>.tex` | the full LaTeX source, ready for Overleaf or any editor |
| `pages/pN.tex` | the transcription of each page; edit one and run `./notes build <name>` to rebuild |
| `figures/` | diagrams cropped from your photos |

Supported files: PDF, JPG, PNG, HEIC (iPhone), WebP. Blank PDF pages are skipped automatically.

## Study material

```bash
./notes extras <name> -t "Course name"
```

builds, next to the notes in `output/<name>/`:

| File | What it is |
|---|---|
| `<name>-bevislista.pdf` | theorems marked as part of the exam proof list, with their proofs (edit `extras/bevislista.txt` to change the selection; a line `källa: <name>` takes the theorems and proofs from another transcribed document, e.g. an official proof list) |
| `<name>-ovningar.pdf` / `-ovningar-losningar.pdf` | all exercises and exam questions, without and with solutions |
| `<name>-flashcards.pdf` / `<name>-anki.txt` | one card per definition and theorem; import the `.txt` in Anki (File → Import). Better card fronts go in `extras/flashcards.txt` |
| `<name>-<x>.pdf` | any hand-written `extras/<x>.tex` body, e.g. a formula sheet or a list of likely slips |

**Proofreading:** `./notes review <name>` makes `<name>-granskning.pdf` (original handwriting next to the transcription for every yellow-highlighted reading) and `<name>-granskning.txt` to fill in.

Long documents also get a table of contents, a list of theorems, and clickable references ("enligt Sats 9.18").
A diagram can be redrawn as TikZ in `drawings/<page>-<fig>.tex` (e.g. `drawings/p70-fig1.tex`); it then replaces the scanned crop.

## Website

```bash
./notes site komplex-2018 -t "Komplex analys 2018"
```

Writes `site/komplex-2018/index.html` (+ `figures/`) and `site/index.html`, a list of every document built so far.
Open `index.html` in a browser, or upload the whole `site/` folder to any static host (GitHub Pages, Netlify, ...).
`site/komplex-2018/artifact.html` is the same page as a single file with the figures inlined.

The page has one view per lecture (`\section`), plus Satser och definitioner, Bevislista (with "Dölj bevisen" to
practise), Övningar (solutions behind "Visa lösning"), Flashcards (marked cards are remembered in the browser), and the
hand-written `extras/*.tex` pages. Search covers all the text, and theorem references link across lectures.
LaTeX is converted with pandoc (`brew install pandoc`); the maths stays TeX and MathJax renders it in the browser,
one view at a time. Rebuild after changing pages or extras; `site/` is not versioned.

## The `./notes` script

The `/transcribe` skill runs it for you, but you can also use it yourself from the project root:

```bash
./notes prepare <name> <PDFs, images or folder> [--pages 1-4] [--keep-blank]
./notes build <name> [-t "Title"] [--partial]
./notes extras <name> [-t "Course"]
./notes site <name> [-t "Course"]
./notes all <name> [-t "Course"]     # build, extras, review and site in one go
```

`-t` is remembered per document (`output/<name>/title.txt`), so after the first time `./notes all <name>` is enough.
`all` stops if the notes don't compile; the other steps run even if one of them fails, and the summary says which.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests
```
