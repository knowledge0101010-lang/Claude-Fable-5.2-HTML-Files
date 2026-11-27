"""Prompt pack tooling: pin, verify, diff and assemble Fable prompt versions.

Prompt "implementation" fails quietly: a 31 KB public release note and a
427 KB full web-app prompt look equally authoritative on disk. This tool makes
the difference measurable — every vendored file is hash-pinned, every version
comparison is section by section, and the assembled runtime pack records which
bytes went into the system message.

    python3 harness/prompt_pack.py verify
    python3 harness/prompt_pack.py diff refs/prompts/fable-5.2/fable-5.0-local-copy.md \
                                    refs/prompts/fable-5.2/web-app-fable-5.2.md
    python3 harness/prompt_pack.py build --behavior refs/prompts/fable-5.2/web-app-fable-5.2.md \
                                          --out reports/pack-fable-5.2.md
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKDIR = ROOT / "refs" / "prompts" / "fable-5.2"
PIN = PACKDIR / "PROMPTS.sha256"

TAGS = re.compile(r"^<([a-z_][a-z0-9_]*)>\s*$", re.M)
HEADINGS = re.compile(r"^(#{1,4})\s+(.+)$", re.M)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> int:
    rows = [line.split("  ", 1) for line in PIN.read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = 0
    for want, name in rows:
        p = PACKDIR / Path(name).name
        got = digest(p) if p.exists() else "missing"
        state = "OK  " if got == want else "FAIL"
        if got != want:
            bad += 1
        print(f"{state} {got[:12]} {p.name}")
    print(f"PASS prompt-pins ({len(rows)} files)" if not bad else f"FAIL prompt-pins ({bad} changed)")
    return 0 if not bad else 1


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def sections(text: str) -> list[str]:
    """Top-level section names, XML tags or markdown headings, in order."""
    found = [(m.start(), f"<{m.group(1)}>") for m in TAGS.finditer(text)]
    found += [(m.start(), m.group(2).strip()) for m in HEADINGS.finditer(text)]
    found.sort()
    out, seen = [], set()
    for _, name in found:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def shape(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "file": _rel(path),
        "sha256": digest(path)[:16],
        "chars": len(text),
        "lines": text.count("\n") + 1,
        "est_tokens": round(len(text) / 3.6),
        "sections": sections(text),
    }


def diff(a: Path, b: Path) -> int:
    sa, sb = shape(a), shape(b)
    set_a = {_norm(x) for x in sa["sections"]}
    set_b = {_norm(x) for x in sb["sections"]}
    added = [s for s in sb["sections"] if _norm(s) not in set_a]
    removed = [s for s in sa["sections"] if _norm(s) not in set_b]
    report = {
        "a": {k: sa[k] for k in ("file", "sha256", "chars", "lines", "est_tokens")},
        "b": {k: sb[k] for k in ("file", "sha256", "chars", "lines", "est_tokens")},
        "growth": {
            "chars": sb["chars"] - sa["chars"],
            "lines": sb["lines"] - sa["lines"],
            "ratio": round(sb["chars"] / max(sa["chars"], 1), 2),
        },
        "sections_added_in_b": added,
        "sections_only_in_a": removed,
        "shared_sections": [s for s in sb["sections"] if _norm(s) in set_a],
        "added_count": len(set_b - set_a),
        "removed_count": len(set_a - set_b),
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


def build(behavior: Path, extra: list[Path], out: Path) -> int:
    parts = [behavior.read_text(encoding="utf-8")]
    for p in extra:
        parts.append(f"\n\n<!-- source: {_rel(p)} sha256:{digest(p)[:16]} -->\n\n" + p.read_text(encoding="utf-8"))
    pack = "".join(parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pack, encoding="utf-8")
    manifest = {
        "builtAt": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "out": _rel(out),
        "chars": len(pack),
        "est_tokens": round(len(pack) / 3.6),
        "sources": [{"file": _rel(p), "sha256": digest(p)[:16]} for p in [behavior, *extra]],
    }
    out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "verify":
        raise SystemExit(verify())
    if args[0] == "shape":
        print(json.dumps(shape(Path(args[1])), indent=1, ensure_ascii=False))
        raise SystemExit(0)
    if args[0] == "diff":
        raise SystemExit(diff(Path(args[1]), Path(args[2])))
    if args[0] == "build":
        behavior = Path(args[args.index("--behavior") + 1])
        out = Path(args[args.index("--out") + 1])
        extra = [Path(args[i + 1]) for i, a in enumerate(args) if a == "--extra"]
        raise SystemExit(build(behavior, extra, out))
    print(__doc__)
    raise SystemExit(2)
