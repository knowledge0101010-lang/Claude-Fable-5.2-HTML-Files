"""Freeze and verify the original collection byte for byte.

"원본 그대로" is a testable claim, not a promise: BASELINE.sha256 records the
sha256 of every file in the supplied commit, and `verify` fails the loop if a
single original byte moved.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_COMMIT = "369dae7fe4102988676f07f147c4bbaefee3ff3a"
BASELINE_FILE = ROOT / "harness" / "BASELINE.sha256"

# 원본(잠금): 스터디 HTML, 스펙 TXT, 스크린샷. 이 셋은 절대 바뀌면 안 된다.
# 나머지는 사이트 인프라(갤러리 빌더·템플릿·index.html)라 개선 대상이다.
def is_locked(name: str) -> bool:
    head = name.split("/", 1)[0]
    if name.startswith("thumbs/"):
        return True
    return "/" not in name and (name[:3].isdigit() and (name.endswith(".html") or name.endswith(".txt")))


def tracked_files(rev: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rev],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(rev: str = BASELINE_COMMIT) -> int:
    rows = [(digest(ROOT / name), name) for name in tracked_files(rev)]
    BASELINE_FILE.write_text(
        "".join(f"{h}  {n}\n" for h, n in rows), encoding="utf-8"
    )
    print(f"wrote {len(rows)} hashes to {BASELINE_FILE.relative_to(ROOT)}")
    return 0


def verify() -> int:
    if not BASELINE_FILE.exists():
        print("no baseline; run: python3 harness/manifest.py build", file=sys.stderr)
        return 2
    rows = [line.split("  ", 1) for line in BASELINE_FILE.read_text(encoding="utf-8").splitlines() if line]
    missing, changed = [], []
    for want, name in rows:
        path = ROOT / name
        if not path.exists():
            missing.append(name)
        elif digest(path) != want:
            changed.append(name)
    locked_missing = [n for n in missing if is_locked(n)]
    locked_changed = [n for n in changed if is_locked(n)]
    infra = [n for n in changed if not is_locked(n)]
    locked_total = sum(1 for _, name in rows if is_locked(name))
    ok = not locked_missing and not locked_changed
    print(f"locked originals: {locked_total - len(locked_missing) - len(locked_changed)}/{locked_total} byte-identical")
    for name in locked_missing:
        print(f"  MISSING  {name}")
    for name in locked_changed:
        print(f"  CHANGED  {name}")
    if infra:
        print(f"  infra changed (allowed, 개선 대상): {', '.join(infra)}")
    print("PASS originals-unchanged" if ok else "FAIL originals-unchanged")
    return 0 if ok else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "build":
        raise SystemExit(build(*sys.argv[2:]))
    raise SystemExit(verify())
