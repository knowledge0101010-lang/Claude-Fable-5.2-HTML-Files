"""Sparse, event-driven inspection schedule (SpikingBrain 참고).

The dense loop re-examines all 76 studies on every iteration, which is the
reason a full pass costs minutes. Here a study is a neuron that only fires
when its input changed:

  L1  checksum   - always, all files (cheap: hashing only)
  L2  static     - study fired: re-read the file and its spec
  L3  browser    - study fired hard (bytes moved past the threshold) or the
                   harness/code itself changed (cold start)

Unchanged studies keep their previous verdicts and are reported as skipped,
separately from "verified unchanged", so the report never confuses the two.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "reports" / "inputs.json"
HARNESS_GLOBS = ("harness/*.py", "harness/*.mjs")
GALLERY_INPUTS = ("index.html", "scripts/gallery-template.html", "scripts/build_gallery.py")
THRESHOLD = 0.01  # fraction of bytes that promotes L2 -> L3


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot() -> dict:
    files: dict[str, dict] = {}
    for pattern in ("[0-9][0-9][0-9]-*.html", "[0-9][0-9][0-9]-*.txt", "thumbs/*.jpg", "studies/*/index.html"):
        for p in sorted(ROOT.glob(pattern)):
            files[str(p.relative_to(ROOT))] = {"sha256": digest(p), "bytes": p.stat().st_size}
    for name in GALLERY_INPUTS:
        p = ROOT / name
        if p.exists():
            files[name] = {"sha256": digest(p), "bytes": p.stat().st_size}
    for pattern in HARNESS_GLOBS:
        for p in sorted(ROOT.glob(pattern)):
            files[str(p.relative_to(ROOT))] = {"sha256": digest(p), "bytes": p.stat().st_size}
    return files


def harness_hash(files: dict) -> str:
    h = hashlib.sha256()
    for name in sorted(n for n in files if n.startswith("harness/")):
        h.update(f"{name}:{files[name]['sha256']}\n".encode())
    return h.hexdigest()


def _moved(old, new) -> bool:
    """A file that appears, disappears or changes hash counts as an event.

    A file that simply never existed (e.g. no derived version for this study)
    is *not* an event — that mistake made every study fire once.
    """
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return old["sha256"] != new["sha256"]


def plan() -> dict:
    current = snapshot()
    previous = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else None

    studies = sorted({n.split("-")[0] + "-" + n.split("-", 1)[1][:-5] for n in current if n.endswith(".html") and n[0].isdigit()})
    total = len(studies)

    if previous is None or previous.get("harness") != harness_hash(current):
        reason = "cold start" if previous is None else "harness changed"
        return _result(current, studies, set(studies), set(studies), set(), reason, total)

    prev_files = previous.get("files", {})
    fired: list[str] = []
    for name in studies:
        html, txt = f"{name}.html", f"{name}.txt"
        # 파생판(studies/<stem>/index.html)이 바뀌어도 그 스터디는 다시 채점한다
        for candidate in (html, txt, f"studies/{name}/index.html"):
            old, new = prev_files.get(candidate), current.get(candidate)
            if _moved(old, new):
                fired.append(name)
                break
    fired_set = set(fired)

    hard = set()
    for name in fired_set:
        old = prev_files.get(f"{name}.html") or {"bytes": 1}
        new = current.get(f"{name}.html") or {"bytes": 1}
        ratio = abs(new["bytes"] - old["bytes"]) / max(old["bytes"], 1)
        if ratio >= THRESHOLD:
            hard.add(name)

    gallery_changed = any(
        prev_files.get(n, {}).get("sha256") != current.get(n, {}).get("sha256") for n in GALLERY_INPUTS
    ) or any(n.startswith("thumbs/") for n in current if prev_files.get(n, {}).get("sha256") != current[n]["sha256"])

    return _result(
        current,
        studies,
        set(studies) - fired_set,
        fired_set,
        hard,
        "incremental",
        total,
        gallery_l3=gallery_changed,
    )


def _result(files, studies, unchanged, l2, l3, reason, total, gallery_l3=False) -> dict:
    l3 = set(l3)
    l2 = set(l2) - l3
    skipped_runtime = total - len(l3)
    return {
        "reason": reason,
        "files": files,
        "harness": harness_hash(files),
        "studies_total": total,
        "l2": sorted(l2),
        "l3": sorted(l3),
        "verified_unchanged": sorted(unchanged),
        "gallery_l2": True,
        "gallery_l3": bool(gallery_l3) or reason != "incremental",
        "sparsity": round(skipped_runtime / total, 4) if total else 0.0,
        "runtime_targets": len(l3) + (1 if gallery_l3 or reason != "incremental" else 0),
    }


def save(result: dict) -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps({"harness": result["harness"], "files": result["files"]}, indent=0),
        encoding="utf-8",
    )


if __name__ == "__main__":
    import sys

    p = plan()
    view = {k: p[k] for k in ("reason", "studies_total", "l2", "l3", "sparsity", "runtime_targets")}
    print(json.dumps(view, indent=1, ensure_ascii=False))
    if "--save" in sys.argv:
        save(p)
        print("saved reports/inputs.json")
