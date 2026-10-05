---
name: transcribe
description: Transcribe handwritten maths and science notes (PDFs, scans or photos) into LaTeX and a compiled PDF. Use when the user runs /transcribe or asks to turn their notes into LaTeX.
argument-hint: "[PDFs, images or folder] [--pages 1-4] [--name NAME] [--title TITLE]"
allowed-tools: Bash(./notes prepare *), Bash(./notes build *), Bash(open output/*), Read, Write, Edit
---

# Transcribe handwritten notes

Arguments: $ARGUMENTS

You do the transcription yourself by reading each page image. The `./notes` script (run from the project root) prepares the images and builds the PDF.

## 1. Work out the inputs

- Inputs: PDFs, images or folders from the arguments, in the order given (folders expand to their PDFs and images sorted by name). With none given, use `notes-in/`. If that is empty, ask the user where the notes are.
- Pages: `--pages` if given (applies to every PDF, e.g. `1-4,7`), otherwise all pages.
- Name: `--name` if given, otherwise the first file's name without extension (or the folder's name). Use lowercase with hyphens, no spaces.
- Title: `--title` if given, otherwise none.

## 2. Prepare

```bash
./notes prepare <name> <inputs...> [--pages 1-4]
```

This splits PDFs into pages and prints each page's source (e.g. `lecture.pdf p3`), image, grid image and the `pN.tex` file to write.

- A page marked "already transcribed" was done in an earlier run: keep it unless the user asked to redo it.
- Blank pages are skipped and listed. Mention them in the report; if the user says one wasn't blank, re-run with `--keep-blank`.
- If more than 15 pages need transcribing, tell the user how many and ask whether to do them all now or a range (`--pages`), since each page uses part of their Claude usage limit.

## 3. Transcribe each page

Read [rules.md](rules.md) once before the first page and follow it exactly.

For each page to transcribe:

1. Read `pages/pN.jpg` and transcribe it.
2. If the page has drawings, graphs or diagrams, read `pages/pN-grid.jpg` to get their positions: the blue lines are at every 0.1 of the width and height, labelled `.1` to `.9`.
3. Write `pages/pN.tex` in the format from rules.md.

Work through the pages in order. Don't summarise a page in the chat; the user sees the result in the PDF.

## 4. Build and fix

```bash
./notes build <name> [-t "<title>"]
```

If it reports LaTeX errors, the line numbers are lines in that page's `pN.tex`. Fix only the syntax that causes the error, without changing the content, and build again. Common causes are listed at the end of rules.md. Stop after 3 rounds and tell the user what is still failing.

When figures were cropped, read each figure PNG once. If a crop cuts off part of the drawing or includes a lot of surrounding text, adjust that `% figure:` line and build again.

## 5. Report

Tell the user, briefly:

- the PDF path (and offer to open it with `open <path>`)
- the uncertain readings from the build output, grouped by page, so they know what to check against the original
- anything you couldn't handle (unreadable sections, drawings you left out)
