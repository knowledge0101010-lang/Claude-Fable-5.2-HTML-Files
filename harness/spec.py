"""Parse the original .txt spec files that sit beside every study.

Sections in the supplied collection are TITLE / PROMPT / DESCRIPTION /
VISUAL TECHNIQUES / INTERACTION MODEL. The supplied gallery builder only
splits four of them, which silently folds INTERACTION MODEL into VISUAL
TECHNIQUES; the parser here keeps all five so the harness can check each
study against every promise its own prompt makes.
"""
from __future__ import annotations

import re
from pathlib import Path

SECTIONS = ("TITLE", "PROMPT", "DESCRIPTION", "VISUAL TECHNIQUES", "INTERACTION MODEL")
_HEAD = re.compile(r"^(" + "|".join(re.escape(s) for s in SECTIONS) + r")[ \t]*$", re.M)
_HEX = re.compile(r"#([0-9A-Fa-f]{6})\b")
_NAMED_KEYS = ("arrow keys", "space", "enter", "escape", "shift", "tab")
_LETTER_PAREN = re.compile(r"\(([A-Z])\)")
_LETTER_PAIR = re.compile(r"\b([A-Z])\s*/\s*([A-Z])\b")
_LETTER_VERB = re.compile(r"\b([A-Z])\s+(?:pulls|fans|skims|selects|toggles|drops|clears)\b")
_DIGIT_RANGE = re.compile(r"\b\d\s*[-\u2013]\s*\d\b")

# Technique phrases -> the signatures the code has to contain to be doing it.
API_SIGNATURES = {
    "canvas": ("canvas 2d", "canvas", "offscreen canvas"),
    "svg": ("svg", "line work"),
    "web audio": ("web audio", "audio"),
    "typed arrays": ("typed array", "typed arrays"),
    "raf": ("requestanimationframe", "animation loop"),
    "pointer": ("pointer", "drag", "click/tap", "click or tap"),
    "keyboard": ("keyboard", "arrow keys"),
    "reduced motion": ("reduced motion", "prefers-reduced-motion"),
    "path 2d": ("path2d", "batched paths"),
    "clip-path": ("clip-path",),
    "svg filter": ("feturbulence", "turbulence", "displacement"),
}
TOKENS = {
    "canvas": ("<canvas",),
    "svg": ("<svg",),
    "web audio": ("AudioContext", "webkitAudioContext"),
    "typed arrays": ("Float32Array", "Uint8Array", "Int32Array", "Float64Array", "Int16Array", "Uint16Array"),
    "raf": ("requestAnimationFrame",),
    "pointer": ("pointerdown", "pointermove", "pointerup"),
    "keyboard": ("keydown", "keyup", "keypress"),
    "reduced motion": ("prefers-reduced-motion",),
    "path 2d": ("Path2D",),
    "clip-path": ("clip-path",),
    "svg filter": ("feTurbulence", "turbulence", "displacement"),
}


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = _HEAD.split(text)
    data: dict = {"_order": []}
    for i in range(1, len(parts) - 1, 2):
        name, body = parts[i], parts[i + 1].strip()
        data[name] = body
        data["_order"].append(name)
    for name in ("PROMPT", "DESCRIPTION"):
        if not data.get(name):
            raise ValueError(f"{path.name}: missing {name}")
    return data


def palette(spec: dict) -> list[str]:
    """Every palette hex the prompt names, lowercased, in order of appearance."""
    seen, out = set(), []
    for h in _HEX.findall(spec.get("PROMPT", "")):
        h = h.lower()
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def techniques(spec: dict) -> list[str]:
    body = spec.get("VISUAL TECHNIQUES", "")
    return [line[2:].strip() for line in body.splitlines() if line.startswith("- ")]


def required_apis(spec: dict) -> list[str]:
    """Which code signatures the prompt's own technique claims imply."""
    body = " ".join(
        [spec.get("VISUAL TECHNIQUES", ""), spec.get("INTERACTION MODEL", ""), spec.get("PROMPT", "")]
    ).lower()
    return sorted({key for key, phrases in API_SIGNATURES.items() if any(p in body for p in phrases)})


def keyboard_keys(spec: dict) -> list[str]:
    body = " ".join([spec.get("INTERACTION MODEL", ""), spec.get("PROMPT", "")])
    low = body.lower()
    keys = [k for k in _NAMED_KEYS if k in low]
    letters = set()
    for a, b in _LETTER_PAIR.findall(body):
        letters.update((a, b))
    letters.update(_LETTER_PAREN.findall(body))
    letters.update(_LETTER_VERB.findall(body))
    keys += sorted(letters)
    if _DIGIT_RANGE.search(body):
        keys.append("1-5")
    return sorted(set(keys))


def wants_reduced_motion(spec: dict) -> bool:
    return "reduced motion" in (
        spec.get("PROMPT", "") + spec.get("INTERACTION MODEL", "")
    ).lower()


def studies(root: Path) -> list[tuple[Path, Path]]:
    return [(p, p.with_suffix(".txt")) for p in sorted(root.glob("[0-9][0-9][0-9]-*.html"))]
