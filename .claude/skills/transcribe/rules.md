# Transcription rules

The student uses the transcription as a clean copy of their own notes, so it must say exactly what the page says.

## Page file format (`pages/pN.tex`)

```latex
% language: swedish
% figure: fig1 0.12 0.40 0.58 0.71
\section{Krafter}
Newtons andra lag: $\vb{F} = m\vb{a}$
\notefigure{fig1}{}
...
```

- Header comments come first, then the LaTeX body.
- `% language:` is `english` or `swedish`, whichever the page is mostly written in. Never translate: Swedish notes stay in Swedish.
- One `% figure:` line per drawing, graph or diagram that can't be written as text or a formula: an id (`fig1`, `fig2`, …) followed by `x0 y0 x1 y1` as fractions of the image width and height (0 = left/top, 1 = right/bottom). Draw the box around the whole drawing, including its axis labels, but keep neighbouring text and lines outside it (only a 1% margin is added). Text inside the box (axis labels, a "Graf:" heading just above) is shown in the image, so don't also write it in the body. Place `\notefigure{figN}{caption}` in the body where the drawing appears. Leave the caption empty unless the page labels the figure.
- The body is inserted into a fixed preamble. Do not write `\documentclass`, `\usepackage`, `\begin{document}`, `\newcommand` or `\def`.

## Faithfulness

- Transcribe what is written. Do not fix mistakes in the maths, add missing steps, finish incomplete derivations or reword sentences. If the student's working is wrong, keep it wrong.
- When you can't read something with confidence, give your best reading wrapped in `\unsure{...}` (works in text and maths). Keep each one short: one word, symbol or small expression. Use it honestly; it is how the student knows what to check.
- Skip text that is crossed out or scribbled over.
- Only if the student asks for corrections afterwards: replace a slip with `\rattat{corrected}{as written}` (prints the correction with a green †, keeps the original in the source).
- Margin notes go in `\marginpar{...}` or a footnote, placed near what they refer to.
- An arrow from a note to something becomes a short parenthetical or footnote near the target.

## Structure

- Main headings become `\section{...}`, smaller or underlined headings become `\subsection{...}`.
- Bullet and numbered lists become `itemize` and `enumerate`. Keep the student's numbering, e.g. `\begin{enumerate}[label=(\alph*)]` for (a), (b), (c).
- Boxed or highlighted results: `\boxed{...}` in maths, or one of these boxes when the page labels the content:
  - `\begin{definition}[optional title] ... \end{definition}`
  - `\begin{theorem}[optional title] ... \end{theorem}` (also for laws, rules, "sats")
  - `\begin{example}[optional title] ... \end{example}` (also for "ex.", "exempel", worked problems)
  - `\begin{note} ... \end{note}` (for "OBS", "NB", remarks)
  - `\begin{proof} ... \end{proof}` (for "bevis", "proof")
  - `\begin{framed}[optional title] ... \end{framed}` for a framed or highlighted area whose label isn't one of the above (e.g. a frame titled "Polär form:"); the title is the page's own label, or empty.

  Only use a box when the page itself marks the content that way (a label, a frame, a different colour).
- A multi-line derivation where lines are aligned or continue with `=` becomes `align*`, with `&` before the relation sign. A single displayed equation becomes `\[ ... \]`. Inline maths uses `$...$`.
- A table becomes `tabular`.
- Keep each displayed line short enough for an A4 page (roughly two fractions and an integral or a bracket). Break long derivations at `=` or `\le` in `align*`, and put long annotations (`\underset{...}`) on short labels or in a separate line, so nothing runs into the margin.

## Notation (packages already loaded)

- Maths: `amsmath`, `amssymb`, `mathtools`, `amsthm`, `bm`, `cancel` (`\cancel{...}` for factors the student strikes through when simplifying), `esint` (`\oiint` for an integral over a closed surface, ∯).
- `physics`: vectors `\vb{F}` (use `\vec{}` only if the student clearly draws arrows), derivatives `\dv{y}{x}`, `\pdv{f}{x}`, `\abs{x}`, `\norm{v}`, `\ket{\psi}`, `\bra{\phi}`, `\expval{A}`.
- `siunitx`: a number with a unit is `\SI{9.81}{\metre\per\second\squared}` or `\qty{}{}`; a bare unit is `\si{\kilo\gram}`. Write decimal numbers as they appear, inside `\num{}` or `\SI{}` so the spacing is right: `\num{7,3}`, `\SI{3,5}{\metre}`. On Swedish pages they print with a comma, on English pages with a point.
- `mhchem`: every chemical formula and reaction goes in `\ce{...}`, e.g. `\ce{2H2 + O2 -> 2H2O}`, `\ce{N2 + 3H2 <=> 2NH3}`, `\ce{Fe^{3+}}`, `\ce{H2O(l)}`.
- Lists: `enumitem`. Colours: `xcolor`.
- No TikZ, and no `\includegraphics` (use `\notefigure`).
- Swedish text can use å, ä, ö directly.

## Look carefully at

- Subscripts vs. separate symbols, exponents, primes vs. apostrophes.
- Easily confused characters: `1/l/I`, `0/O/o`, `u/v/ν`, `x/×/χ`, `t/+`, `a/α`, `B/β/ß`, `p/ρ`, `w/ω`, `n/η`, `e/ε/∈`, `z/2`, `5/S`, `g/9/q`.
- Which variable is being integrated or differentiated, and the limits on integrals and sums.
- Whether a fraction bar covers the whole expression.
- Use the meaning of the surrounding maths to resolve ambiguous symbols, but never to change what is written.

## Fixing LaTeX errors

Common causes: unbalanced braces or `\left`/`\right`, `&` or `\\` outside an alignment environment, maths commands outside maths mode, a blank line inside `align*` or `\[ \]`, an environment that isn't closed, unsupported `\ce` syntax, and `%`, `_` or `#` used as text without escaping. Fix only what causes the error; keep the content the same.

## This student's notation

Learned from the first pages of their notes; follow these unless a page clearly shows otherwise.

- Partial derivatives are written with a straight d (`du/dx`). Keep them as `\frac{du}{dx}`; don't change them to `\partial`.
- The angle symbol that looks like φ is `\varphi`.
- A curly capital L in "Log" (𝓛og) means an arbitrary branch of the logarithm, distinct from `\operatorname{Log}` (principal branch) and `\log` (some branch). Write it as `\mathcal{L}og`.
- Lectures start with "Föreläsning D/M" (a date), which becomes `\section{Föreläsning D/M}`; "Storgruppsövning D/M" likewise. Boxed exercise numbers like `[1.2e]` become `\fbox{1.2e}`.
- Underlined key terms in running text become `\emph{...}`. Coloured ink keeps its colour: red `red!70!black`, blue `blue!60!black`, pink `magenta!80!black`.
- "Obs!", "Notera:" become `note` boxes; "Sats", "Proposition", named results become `theorem` boxes with the page's label as title; "Bevis:" becomes `proof`.
