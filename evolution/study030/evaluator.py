"""Evaluator for the integrated AlphaEvolve run — target A: the 030 study.

Scores a candidate HTML string on the same contract the regression harness uses,
plus structural gates that a browser would otherwise catch only at runtime:

  palette (45%)  every hex the original .txt names must appear
  api     (35%)  the techniques the prompt claims must be present in code
  a11y    (10%)  lang / title / viewport / reduced-motion
  shape   (10%)  single document, canvas or svg, no external requests, size cap

The candidate never replaces the original. It is written to a scratch file and
discarded; promotion is a separate, gated step.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
import spec as S  # noqa: E402

import os
SPEC = Path(os.environ.get("STUDY_SPEC") or (ROOT / "030-rose-window.txt"))
MAX_BYTES = 140_000


def extract(program_path: str) -> str:
    text = Path(program_path).read_text(encoding="utf-8")
    m = re.search(r'HTML = r"""(.*?)"""', text, re.S)
    return m.group(1) if m else ""


def evaluate(program_path: str) -> dict:
    page = extract(program_path)
    if not page.strip():
        return {"combined_score": 0.0, "error": "no HTML block"}
    sp = S.parse(SPEC)
    low = page.lower()

    palette = S.palette(sp)
    pal_hits = [h for h in palette if h in low]
    apis = S.required_apis(sp)
    api_hits = [a for a in apis if any(t.lower() in low for t in S.TOKENS[a])]

    a11y = {
        "lang": bool(re.search(r"<html[^>]+lang=", low)),
        "title": bool(re.search(r"<title>[^<]+</title>", low)),
        "viewport": 'name="viewport"' in low,
        "reduced_motion": "prefers-reduced-motion" in low,
        "keyboard": "keydown" in low,
    }

    shape = {
        "closes": "</html>" in low,
        "graphics": ("<canvas" in low) or ("<svg" in low),
        "no_external": not re.search(r'(?:src|href)\s*=\s*["\']https?://', page, re.I),
        "size": len(page.encode("utf-8")) <= MAX_BYTES,
        "script": "<script" in low,
    }

    score_pal = len(pal_hits) / max(len(palette), 1)
    score_api = len(api_hits) / max(len(apis), 1)
    score_a11y = sum(a11y.values()) / len(a11y)
    score_shape = sum(shape.values()) / len(shape)
    combined = 0.45 * score_pal + 0.35 * score_api + 0.10 * score_a11y + 0.10 * score_shape

    return {
        "combined_score": round(combined, 4),
        "palette": round(score_pal, 4),
        "api": round(score_api, 4),
        "a11y": round(score_a11y, 4),
        "shape": round(score_shape, 4),
        "missing_palette": [h for h in palette if h not in low],
        "missing_api": [a for a in apis if a not in api_hits],
        "bytes": len(page.encode("utf-8")),
    }


if __name__ == "__main__":
    print(evaluate(sys.argv[1]))
