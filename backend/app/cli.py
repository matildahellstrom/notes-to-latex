"""Command line, used by the /transcribe skill (run through the ./notes wrapper):

    ./notes prepare <name> lecture.pdf [--pages 1-4]  split into pages for transcription
    ./notes build <name> [-t "Title"]                 crop figures, assemble and compile
    ./notes extras <name> [-t "Course"]               bevislista, övningar, flashcards, extras/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.pipeline.run import build, prepare_pages
from app.pipeline.preprocess import SUPPORTED

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"


def expand_inputs(paths: list[Path]) -> list[Path]:
    """Files as given; folders expand to their PDFs and images sorted by name."""
    files = []
    for p in paths:
        if p.is_dir():
            files += sorted((f for f in p.iterdir() if f.suffix.lower() in SUPPORTED),
                             key=lambda f: f.name.lower())
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(f"not found: {p}")
    return files


def cmd_prepare(args) -> int:
    files = expand_inputs(args.inputs)
    if not files:
        print("No PDFs or images found.", file=sys.stderr)
        return 1
    out_dir = OUTPUT_DIR / args.name
    result = prepare_pages(files, out_dir, args.pages, args.keep_blank)
    print(f"Prepared {len(result.pages)} page(s) in {out_dir}")
    if result.blank:
        print("Skipped blank page(s): " + ", ".join(result.blank) + "  (use --keep-blank to include)")
    if result.stale:
        print("Set aside old transcriptions that no longer match their page: " + ", ".join(result.stale))
    for p in result.pages:
        status = "already transcribed" if p.transcription.exists() else "to transcribe"
        print(f"  page {p.number}: {p.source}")
        print(f"    image: {p.image}")
        print(f"    grid:  {p.grid}")
        print(f"    write: {p.transcription}  ({status})")
    return 0 if result.pages else 1


def cmd_build(args) -> int:
    out_dir = OUTPUT_DIR / args.name
    result = build(out_dir, args.title, args.partial)
    if result.missing:
        print("Not transcribed yet: page(s) " + ", ".join(map(str, result.missing)))
        return 1
    print(f"LaTeX: {result.tex}")
    if result.ok:
        print(f"PDF:   {result.pdf}")
    else:
        print("PDF:   not created, LaTeX errors:")
        for n, errs in result.page_errors.items():
            print(f"  page {n} ({out_dir / 'pages' / f'p{n}.tex'}):")
            for e in errs:
                print("    " + e.replace("\n", "\n    "))
        for e in result.errors:
            print("  " + e.replace("\n", "\n  "))
    if result.uncertain:
        print("Uncertain readings (highlighted yellow):")
        for n, words in result.uncertain.items():
            print(f"  page {n}: " + " | ".join(words))
    figures = sorted((out_dir / "figures").glob("*.png"))
    if figures:
        print("Figures: " + ", ".join(str(f) for f in figures))
    return 0 if result.ok else 2


def cmd_extras(args) -> int:
    from app.pipeline.extras import build_extras
    out_dir = OUTPUT_DIR / args.name
    results = build_extras(out_dir, args.title or args.name)
    failed = 0
    for name, r in results.items():
        if isinstance(r, Path):
            print(f"  {name}: {r}")
        elif r.ok:
            print(f"  {name}: {r.pdf}")
        else:
            failed += 1
            print(f"  {name}: FAILED")
            for e in r.errors:
                print("    " + e.replace("\n", "\n    "))
    return 2 if failed else 0


def cmd_review(args) -> int:
    from app.pipeline.review import build_review
    result, txt, n = build_review(OUTPUT_DIR / args.name, args.title or args.name)
    if result is None:
        print("No uncertain readings left.")
        return 0
    if not result.ok:
        print("Review sheet failed:")
        for e in result.errors:
            print("  " + e.replace("\n", "\n  "))
        return 2
    print(f"{n} uncertain readings")
    print(f"  look at:  {result.pdf}")
    print(f"  fill in:  {txt}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notes", description="Handwritten notes to LaTeX.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="split PDFs/photos into pages for transcription")
    p.add_argument("name", help="document name (output folder)")
    p.add_argument("inputs", nargs="+", type=Path, help="PDFs, photos or folders, in page order")
    p.add_argument("--pages", help="PDF pages to include, e.g. 1-3,5 (default: all)")
    p.add_argument("--keep-blank", action="store_true", help="don't skip empty pages")
    p.set_defaults(func=cmd_prepare)

    b = sub.add_parser("build", help="assemble transcribed pages and compile the PDF")
    b.add_argument("name", help="document name (output folder)")
    b.add_argument("-t", "--title", default="", help="title printed at the top")
    b.add_argument("--partial", action="store_true",
                   help="build only the pages transcribed so far (up to the first missing one)")
    b.set_defaults(func=cmd_build)

    e = sub.add_parser("extras", help="study material: bevislista, övningar, flashcards, extras/*.tex")
    e.add_argument("name", help="document name (output folder)")
    e.add_argument("-t", "--title", default="", help="course name used in the titles")
    e.set_defaults(func=cmd_extras)

    v = sub.add_parser("review", help="review sheet for the remaining uncertain readings")
    v.add_argument("name", help="document name (output folder)")
    v.add_argument("-t", "--title", default="", help="course name used in the title")
    v.set_defaults(func=cmd_review)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
