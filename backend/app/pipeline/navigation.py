"""Navigation for long documents: a list of theorems and clickable references to them.

Theorem titles such as "Rouchés sats (Sats 9.18)" become targets; references elsewhere in the
text such as "enligt Prop 9.18" or "(sats 9.18)" become links to them.
"""

from __future__ import annotations

import re

# "Sats 9.18", "Prop.\ 9.11a", "Proposition 3.4F", "Kor 5.8", "Korollarium 8.6", "prop 1.3 R"
REF = re.compile(
    r"\b(?P<kind>[Ss]ats|[Pp]rop(?:osition)?|[Kk]or(?:oll[ao]rium)?)\.?(?:\\ |\s)*"
    r"(?P<num>\d+\.\d+)(?:\.?\s?(?P<suffix>[A-Za-z])\b)?")
THEOREM_START = re.compile(r"\\begin\{theorem\}(?:\[(?P<title>(?:[^\[\]]|\[[^\]]*\])*)\])?")


def ref_key(num: str, suffix: str | None) -> str:
    return num + (suffix or "").lower()


def theorem_targets(bodies: list[str]) -> dict[str, tuple[int, int]]:
    """key -> (page index, theorem index on that page) of the first theorem titled with it."""
    targets: dict[str, tuple[int, int]] = {}
    for p, body in enumerate(bodies):
        for t, m in enumerate(THEOREM_START.finditer(body)):
            for ref in REF.finditer(m.group("title") or ""):
                targets.setdefault(ref_key(ref["num"], ref["suffix"]), (p, t))
    return targets


def resolve(key: str, targets: dict) -> str | None:
    if key in targets:
        return key
    if key[-1:].isalpha() and key[:-1] in targets:  # "7.25b" -> "7.25"
        return key[:-1]
    return None


def add_navigation(bodies: list[str], page_numbers: list[int]) -> list[str]:
    """Index every theorem and link references to numbered theorems."""
    targets = theorem_targets(bodies)
    anchor_of = {pos: f"ref-{key}" for key, pos in targets.items()}
    out = []
    for p, body in enumerate(bodies):
        # Theorem headers (with their index entries) are set aside so references inside
        # titles are not turned into links.
        protected: list[str] = []

        def mark_theorem(m: re.Match) -> str:
            t = len(protected)
            title = (m.group("title") or "").strip()
            entry = title or f"Sats (s.\\ {page_numbers[p]})"
            if not entry[0].isalpha():  # "2.17", "(2.3 PB)" -> "Sats 2.17"
                entry = "Sats " + entry
            text = m.group(0) + f"\\theoremindex{{{entry}}}"
            if (p, t) in anchor_of:
                text += f"\\hypertarget{{{anchor_of[(p, t)]}}}{{}}"
            protected.append(text)
            return f"\x00{t}\x00"

        body = THEOREM_START.sub(mark_theorem, body)

        def link(m: re.Match) -> str:
            key = resolve(ref_key(m["num"], m["suffix"]), targets)
            return f"\\hyperlink{{ref-{key}}}{{{m.group(0)}}}" if key else m.group(0)

        body = REF.sub(link, body)
        body = re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], body)
        out.append(body)
    return out
