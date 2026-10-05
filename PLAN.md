# Handwritten Notes → LaTeX: Project Plan

## 1. Goal

Turn PDFs, scans or photos of handwritten maths and science notes into clean, compilable LaTeX (`.tex`) plus a rendered PDF, with an easy way to review and correct the result. No paid API: the transcription runs in Claude Code on the user's existing Claude subscription.

**Success criteria**
- More than 95% of transcribed pages compile after the fix loop.
- Equations, chemistry, units and structure (headings, lists, boxed results) come through correctly.
- Fixing a mistake is quick: uncertain readings are highlighted and listed per page.

## 2. How it works

```
Notes in notes-in/ (PDF, or JPG/PNG/HEIC/WebP photos)
   │
   ▼  ./notes prepare <name> <images>
Preprocess ── split PDFs into pages, skip blank ones, fix orientation,
   │          downscale, boost contrast,
   │          save pN.jpg + pN-grid.jpg (grid for figure coordinates)
   ▼
Transcribe ── Claude Code (/transcribe skill) reads each page image
   │          and writes pN.tex: header (language, figure boxes) + LaTeX body
   ▼  ./notes build <name>
Assemble ──── insert bodies into the fixed preamble, crop figures (paper whitened)
   ▼
Compile ───── XeLaTeX via latexmk (TeX Live)
   │   └── on error: per-page errors with line numbers in pN.tex;
   │       Claude fixes the syntax and builds again (max 3 rounds)
   ▼
Result ────── output/<name>/<name>.pdf + .tex + figures/
```

### Why Claude rather than classic OCR
Classic OCR (Tesseract) can't handle maths. Specialized maths OCR (e.g. Mathpix) is very good at single equations but weaker at whole pages with mixed prose, diagrams, arrows and margin notes. Claude reads the whole page in context, so it can tell a subscript from a messy letter by its meaning, and it understands layout.

### Why Claude Code instead of the API
The API bills per page on top of a Claude subscription. Running the transcription inside Claude Code uses the subscription that is already paid for, with the same model quality. The trade-off is that transcription happens in a Claude Code session, not in a standalone app.

## 3. Handling maths and science content

Every page uses a **fixed preamble** ([preamble.tex](backend/app/templates/preamble.tex)), so the output is predictable:

| Content | Package / convention |
|---|---|
| Equations, aligned derivations | `amsmath`, `amssymb`, `mathtools` (`align*`, `cases`) |
| Vectors, derivatives, bra-ket | `physics` (`\vb{F}`, `\dv{}{}`, `\pdv{}{}`, `\ket{}`) |
| Units | `siunitx` (`\SI{9,82}{\metre\per\second\squared}`); the decimal marker follows the page language |
| Chemistry formulas and reactions | `mhchem` (`\ce{2H2 + O2 -> 2H2O}`) |
| Boxed answers | `\boxed{}` |
| Definitions, theorems, examples, notes | coloured `tcolorbox` environments, named in the page's language (Sats, Exempel, …) |
| Proofs | `amsthm` `proof` |
| Diagrams and graphs | cropped from the photo as images; TikZ redraw as an optional later feature |
| Unreadable or uncertain bits | `\unsure{...}`, highlighted yellow and listed after each build |

The transcription rules live in [rules.md](.claude/skills/transcribe/rules.md): transcribe faithfully (never fix the maths), keep the page structure, skip crossed-out text, mark uncertain readings.

## 4. Tech stack

| Layer | Choice | Reason |
|---|---|---|
| Transcription | **Claude Code** with a project skill (`/transcribe`) | Uses the existing subscription; no API key or per-page cost |
| Pipeline | **Python** (Pillow, pillow-heif, pypdfium2 for PDFs) behind a `./notes` script | Image handling, figure cropping, assembly, error reporting |
| LaTeX compile | **XeLaTeX via latexmk** (TeX Live 2025, already installed); Tectonic as a fallback | Every needed package is present; XeLaTeX handles å/ä/ö natively |
| Review UI (later) | Local web page: page image, LaTeX editor, rebuild button | No API needed; edits and rebuilds only |

## 5. Project structure

```
ClaudeTest3okt/
├── notes                        # ./notes prepare | build
├── notes-in/                    # put photos here
├── output/<name>/               # pages/, figures/, <name>.tex, <name>.pdf
├── .claude/skills/transcribe/
│   ├── SKILL.md                 # the /transcribe workflow
│   └── rules.md                 # transcription rules
├── backend/
│   ├── app/
│   │   ├── cli.py
│   │   ├── pipeline/
│   │   │   ├── preprocess.py    # PDF split, orientation, resize, contrast, grid
│   │   │   ├── assemble.py      # page files, preamble, figure cropping
│   │   │   ├── compile.py       # latexmk/XeLaTeX, error extraction
│   │   │   └── run.py           # prepare and build steps
│   │   └── templates/preamble.tex
│   └── tests/
└── PLAN.md
```

## 6. Milestones

**M1: Core pipeline**: built and tested on a sample page.
- `/transcribe` in Claude Code goes from photos to PDF; `./notes prepare` and `./notes build` do the non-AI work.
- Done when 5 pages of the user's own notes compile and look right.

**M2: More input types**: PDF support built.
- PDFs are split into pages, blank pages skipped, `--pages` picks a range; re-runs keep transcriptions attached to their source page.
- Still open: optional perspective correction for photos taken at an angle.

**M3: Review UI (local)**
- Page image | LaTeX editor | PDF preview, with `\unsure{}` spots highlighted and click-to-jump.
- Rebuild button; export `.tex`, `.pdf` and `.zip`.

**M4: Figures and diagrams**
- Basic cropping is done.
- Optional: "redraw as TikZ" for simple graphs and circuit diagrams.

**Study material**: built.
- `./notes extras`: bevislista, practice exercises (with and without solutions), flashcards (PDF + Anki), hand-written extras (formula sheet, errata).
- Table of contents, list of theorems and clickable theorem references in long documents; TikZ redrawings replace scanned diagrams.

**M5: Library and quality**
- Notes organised by course and subject.
- A small test set of the user's own pages with hand-checked LaTeX, used to tune rules.md.
- Optional personal glossary (own notation and abbreviations) added to rules.md.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Messy handwriting is misread | `\unsure{}` flags, listed per page after each build |
| Claude "corrects" the maths | Explicit faithfulness rule; test set catches regressions |
| LaTeX doesn't compile | Fixed preamble; per-page errors with exact line numbers; fix loop |
| Phone photos (shadows, angle) | Contrast boost now; perspective correction in M2 |
| Long documents use up subscription limits | Pages already transcribed are kept and skipped on re-runs |
| Privacy | Everything stays local except the page images Claude reads in the session |

## 8. Decisions

1. **Platform: local first.** Runs on the laptop.
2. **Transcription: Claude Code, no API key.** No per-page cost; runs inside a Claude Code session.
3. **Diagrams: cropped as images.** TikZ redrawing stays an optional later feature (M4).
4. **Output style: notes style.** Coloured boxes for definitions, theorems, examples and notes; `\boxed{}` for final answers.
5. **Input: PDFs** (photos also work).
6. **Languages: English and Swedish.** Each page's language is detected and set with `\selectlanguage`; box names and decimal markers follow it. Never translated.
