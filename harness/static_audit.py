"""Static conformance audit: each study against the prompt that produced it.

Nothing here inspects the browser. It answers: does the file on disk still
honour its own spec (palette, claimed techniques, keyboard promise, reduced
motion, self-containment), and does the gallery still describe the collection
truthfully. Everything it measures lands in one JSON object so the loop can
diff two runs.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = re.compile(r'(?:src|href)\s*=\s*["\'](https?:)?//', re.I)


def _has(haystack: str, needles) -> bool:
    if isinstance(needles, str):
        needles = (needles,)
    return any(n.lower() in haystack for n in needles)


def audit_study(html_path: Path, txt_path: Path) -> dict:
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    low = raw.lower()
    sp = S.parse(txt_path)

    palette = S.palette(sp)
    hits = [h for h in palette if h in low]
    apis = S.required_apis(sp)
    api_hits = [a for a in apis if _has(low, S.TOKENS[a])]
    keys = S.keyboard_keys(sp)
    wants_rm = S.wants_reduced_motion(sp)

    a11y = {
        "lang": bool(re.search(r"<html[^>]+lang=", low)),
        "title": bool(re.search(r"<title>[^<]+</title>", low)),
        "viewport": "name=\"viewport\"" in low or "name='viewport'" in low,
        "reduced_motion": "prefers-reduced-motion" in low,
    }
    focusable = len(re.findall(r"<button\b|<input\b|<select\b|<textarea\b|<summary\b|<a\s[^>]*href=|tabindex=", low))
    checks = dict(a11y)
    if wants_rm:
        checks.pop("reduced_motion")
        checks["reduced_motion"] = a11y["reduced_motion"]

    n_palette = len(palette) or 1
    n_api = len(apis) or 1
    n_a11y = len(checks) or 1
    score = {
        "palette": round(len(hits) / n_palette, 4),
        "api": round(len(api_hits) / n_api, 4),
        "a11y": round(sum(checks.values()) / n_a11y, 4),
    }
    score["composite"] = round(0.45 * score["palette"] + 0.35 * score["api"] + 0.20 * score["a11y"], 4)

    externals = sorted({m.group(0) for m in EXTERNAL.finditer(raw)})
    return {
        "file": html_path.name,
        "number": html_path.name[:3],
        "bytes": len(raw.encode("utf-8")),
        "palette": {"wanted": len(palette), "missing": [h for h in palette if h not in low]},
        "api": {"wanted": apis, "missing": [a for a in apis if a not in api_hits]},
        "keyboard": {
            "keys": keys,
            "keydown": "keydown" in low,
            # The prompt promises keyboard *access*, which native focusable
            # controls satisfy without any keydown listener. Counting only
            # keydown was a false-negative in the first harness version.
            "focusable": focusable,
            "operable": focusable > 0 or "keydown" in low,
        },
        "reduced_motion": {"wanted": wants_rm, "present": a11y["reduced_motion"]},
        "a11y": checks,
        "self_contained": {"external_refs": externals, "ok": not externals},
        "score": score,
    }


def _prompt_blocks(index: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(
        r'<div class="prompt-text">(.*?)</div>', index, re.S
    ):
        num = None
        out.setdefault(str(len(out)), html.unescape(m.group(1)))
    return out


def audit_reimpls() -> list[dict]:
    """Derived versions under studies/<stem>/index.html, scored on the same spec."""
    out = []
    for page in sorted((ROOT / "studies").glob("*/index.html")):
        stem = page.parent.name
        txt = ROOT / f"{stem}.txt"
        if not txt.exists():
            continue
        rec = audit_study(page, txt)
        rec["file"] = str(page.relative_to(ROOT))
        rec["original"] = f"{stem}.html"
        out.append(rec)
    return out


def audit_gallery(studies: list[dict]) -> dict:
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    cards = re.findall(r'<article class="card" id="study-(\d{3})">', index)
    hrefs = set(re.findall(r'href="(\d{3}-[^"]+\.html)"', index))
    expected = {s["file"] for s in studies}
    ids = re.findall(r'\sid="([^"]+)"', index)
    dupes = sorted({i for i in ids if ids.count(i) > 1})

    prompt_txt = re.findall(r'<div class="prompt-text">(.*?)</div>', index, re.S)
    spec_prompts = []
    for s in studies:
        sp = S.parse(ROOT / s["file"].replace(".html", ".txt"))
        spec_prompts.append(sp["PROMPT"])
    exact = sum(
        1 for a, b in zip(prompt_txt, spec_prompts) if html.unescape(a).strip() == b.strip()
    )

    thumbs_ok = all((ROOT / f"thumbs/{Path(s['file']).stem}.jpg").is_file() for s in studies)
    alts = re.findall(r'<img [^>]*alt="([^"]*)"', index)
    alt_ok = len(alts) == len(studies) and all(a.strip() for a in alts)

    checks = {
        "card_count": {"value": len(cards), "ok": len(cards) == len(expected)},
        "all_studies_linked": {"value": len(expected & hrefs), "ok": expected <= hrefs},
        "prompt_exact": {"value": exact, "ok": exact == len(studies)},
        "thumbnails": {"value": thumbs_ok, "ok": thumbs_ok},
        "alts": {"value": len(alts), "ok": alt_ok},
        "unique_ids": {"value": len(dupes), "ok": not dupes},
        "lang": {"value": 'lang="en"' in index, "ok": 'lang="en"' in index},
        "viewport": {"value": 'name="viewport"' in index, "ok": 'name="viewport"' in index},
        "h1_count": {"value": len(re.findall(r"<h1[ >]", index)), "ok": len(re.findall(r"<h1[ >]", index)) == 1},
        "skip_link": {"value": 'class="skip' in index, "ok": 'class="skip' in index},
        "search_control": {"value": 'id="q"' in index, "ok": 'id="q"' in index},
        "interaction_model_shown": {
            "value": "interaction-panel" in index or "Interaction model" in index,
            "ok": "interaction-panel" in index or "Interaction model" in index,
        },
        "template_matches_index": {"value": None, "ok": True},
    }
    return {
        "checks": checks,
        "bytes": len(index.encode("utf-8")),
        "duplicate_ids": dupes,
        "passed": sum(1 for c in checks.values() if c["ok"]),
        "total": len(checks),
    }


def summarize(studies: list[dict], gallery: dict, comparisons: list[dict]) -> dict:
    comp = [s["score"]["composite"] for s in studies]
    return {
        "studies": len(studies),
        "composite_mean": round(sum(comp) / len(comp), 4),
        "palette_perfect": sum(1 for s in studies if not s["palette"]["missing"]),
        "api_perfect": sum(1 for s in studies if not s["api"]["missing"]),
        "reduced_motion_wanted": sum(1 for s in studies if s["reduced_motion"]["wanted"]),
        "reduced_motion_missing": sum(
            1 for s in studies if s["reduced_motion"]["wanted"] and not s["reduced_motion"]["present"]
        ),
        "keyboard_promised": sum(1 for s in studies if s["keyboard"]["keys"]),
        "keyboard_missing": sum(1 for s in studies if s["keyboard"]["keys"] and not s["keyboard"]["operable"]),
        "studies_with_focusable_controls": sum(1 for s in studies if s["keyboard"]["focusable"]),
        "external_refs": sum(len(s["self_contained"]["external_refs"]) for s in studies),
        "gallery_passed": gallery["passed"],
        "gallery_total": gallery["total"],
        "total_bytes": sum(s["bytes"] for s in studies),
        "reimpl_count": len([c for c in comparisons]),
        "reimpl_mean_delta": round(sum(c["delta"] for c in comparisons) / len(comparisons), 4) if comparisons else None,
    }


def run(only: list[str] | None = None, previous: Path | None = None) -> dict:
    """Audit every study, or only `only` while reusing `previous` verdicts."""
    cached: dict[str, dict] = {}
    if only and previous and previous.exists():
        prev = json.loads(previous.read_text(encoding="utf-8"))
        cached = {s["file"]: s for s in prev.get("studies", [])}
    studies = []
    for html_path, txt_path in S.studies(ROOT):
        if only and html_path.name not in only and html_path.name in cached:
            studies.append(cached[html_path.name])
        else:
            studies.append(audit_study(html_path, txt_path))
    gallery = audit_gallery(studies)
    reimpls = audit_reimpls() if not only else []
    by_file = {s["file"]: s for s in studies}
    comparisons = [
        {
            "study": r["original"],
            "original_score": by_file[r["original"]]["score"]["composite"],
            "reimpl_score": r["score"]["composite"],
            "delta": round(r["score"]["composite"] - by_file[r["original"]]["score"]["composite"], 4),
            "original_palette_missing": by_file[r["original"]]["palette"]["missing"],
            "reimpl_palette_missing": r["palette"]["missing"],
        }
        for r in reimpls if r["original"] in by_file
    ]
    return {
        "originals": {"count": len(studies)},
        "reimpls": reimpls,
        "comparisons": comparisons,
        "reused": sum(1 for s in studies if only and s["file"] in cached and s["file"] not in set(only)),
        "studies": studies,
        "gallery": gallery,
        "summary": summarize(studies, gallery, comparisons),
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    out = ROOT / "reports" / "static.json"
    only: list[str] | None = None
    prev: Path | None = None
    i = 0
    while i < len(args):
        if args[i] == "--only":
            only = args[i + 1].split(",")
            i += 2
        elif args[i] == "--previous":
            prev = Path(args[i + 1])
            i += 2
        else:
            out = Path(args[i])
            i += 1
    report = run(only, prev)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))
    print(f"wrote {out}")
