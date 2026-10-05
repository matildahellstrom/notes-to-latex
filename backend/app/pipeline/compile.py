"""Compile .tex to PDF with XeLaTeX (via latexmk) and extract readable errors."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

COMPILE_TIMEOUT = 120  # seconds


@dataclass
class CompileResult:
    ok: bool
    pdf: Path | None
    errors: list[str]
    log: str


def find_engine() -> list[str]:
    """Prefer latexmk + XeLaTeX (TeX Live); fall back to Tectonic if that is all there is."""
    if shutil.which("latexmk") and shutil.which("xelatex"):
        return ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
                "-file-line-error", "-quiet"]
    if shutil.which("tectonic"):
        return ["tectonic", "--keep-logs"]
    raise RuntimeError("No LaTeX engine found. Install MacTeX (latexmk + xelatex) or Tectonic.")


def compile_tex(tex_path: Path) -> CompileResult:
    cmd = find_engine() + [tex_path.name]
    try:
        proc = subprocess.run(cmd, cwd=tex_path.parent, capture_output=True, text=True,
                              errors="replace", timeout=COMPILE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, ["Compilation timed out."], "")

    log_path = tex_path.with_suffix(".log")
    log = log_path.read_text(errors="replace") if log_path.exists() else proc.stdout + proc.stderr
    pdf = tex_path.with_suffix(".pdf")
    ok = proc.returncode == 0 and pdf.exists()
    return CompileResult(ok, pdf if pdf.exists() else None, [] if ok else extract_errors(log), log)


def extract_errors(log: str, limit: int = 5) -> list[str]:
    """Pull the first few error messages (with the line they point at) out of a TeX log."""
    lines = log.splitlines()
    errors: list[str] = []
    for i, line in enumerate(lines):
        if re.match(r"^(\./)?[^:\s]+\.tex:\d+: ", line) or line.startswith("! "):
            context = [l for l in lines[i : i + 4] if l.strip()]
            msg = "\n".join(context)
            if msg not in errors:
                errors.append(msg)
        if len(errors) >= limit:
            break
    return errors or ["Unknown LaTeX error. Last log lines:\n" + "\n".join(lines[-15:])]


def clean_aux(tex_path: Path) -> None:
    for ext in (".aux", ".fdb_latexmk", ".fls", ".out", ".xdv", ".synctex.gz"):
        tex_path.with_suffix(ext).unlink(missing_ok=True)
