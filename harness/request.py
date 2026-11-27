"""참고 요청 연산 (RRC) — reference-pinned request computation.

One request goes through six stages and cannot spend compute before stage 4
passes. The point is that today's failures (missing credentials, unknown CLI
contract, a package import chain nobody read, a sandbox that cannot nest) were
all detectable without calling a model.

    python3 harness/request.py run requests/study-030.yaml
    python3 harness/request.py run requests/lewm-collapse.yaml --execute

Stages:
  1 spec       요청 카드를 해석하고 합격/반증 조건이 있는지 확인
  2 references 참고 파일·URL의 sha256을 고정
  3 plan       실행 단위(스터디 채점 / 실험)와 명령을 확정
  4 preflight  디스크·모듈·경로·명령을 실제로 찔러보고 불가면 여기서 중단
  5 execute    실행 (--execute 없으면 계획만)
  6 judge      지표를 뽑아 합격 조건과 대조하고 매니페스트에 기록

산출물: reports/requests/<id>.json — 참고 해시, 판정, 지표, 소요 시간.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "reports" / "requests"


# --------------------------------------------------------------------------- #
# minimal YAML reader: the cards only need flat scalars, lists of scalars and
# one level of mappings, so avoid a hard pyyaml dependency in the harness.
# --------------------------------------------------------------------------- #
def load_card(path: Path) -> dict:
    try:
        import yaml  # noqa: F401
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except ImportError:
        pass
    card: dict = {}
    section = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            card[section] = {}
            continue
        if line.startswith("  - "):
            card.setdefault("_lists", {}).setdefault(section, []).append(line[4:].strip().strip('"'))
            continue
        if line.startswith("  ") and ":" in line:
            k, v = line.split(":", 1)
            card.setdefault(section, {})[k.strip()] = v.strip().strip('"')
    for sec, items in card.pop("_lists", {}).items():
        if isinstance(card.get(sec), dict) and not card[sec]:
            card[sec] = items
    return card


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(dotted)
    return cur


def disk_free_mb(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.free // (1 << 20)


# --------------------------------------------------------------------------- #
# stages
# --------------------------------------------------------------------------- #
def stage_spec(card: dict) -> tuple[bool, str]:
    missing = [k for k in ("id", "kind", "goal") if not card.get(k)]
    if missing:
        return False, f"카드에 {', '.join(missing)} 없음"
    if card["kind"] == "experiment" and not card.get("falsifier"):
        return False, "실험에는 반증 조건(falsifier)이 필요하다"
    if not card.get("acceptance"):
        return False, "합격 조건(acceptance)이 없으면 실행하지 않는다"
    return True, f"{card['kind']} · {card['goal'][:60]}"


def stage_references(card: dict) -> tuple[bool, str]:
    rows = []
    for ref in card.get("references") or []:
        p = Path(ref)
        p = p if p.is_absolute() else ROOT / p
        if not p.exists():
            rows.append({"ref": ref, "status": "missing"})
            continue
        rows.append({"ref": ref, "sha256": digest(p)[:16], "bytes": p.stat().st_size})
    card["_refs"] = rows
    ok = bool(rows) and all(r.get("status") != "missing" for r in rows)
    return ok, f"{sum(1 for r in rows if r.get('sha256'))}/{len(rows)} 참고 고정"


def stage_plan(card: dict) -> tuple[bool, str]:
    run = card.get("run") or {}
    if not run.get("command"):
        return False, "run.command 없음"
    if not run.get("metrics_file") and "--json" not in run["command"]:
        # stdout-JSON mode is allowed, but the card must say so explicitly
        if run.get("metrics_stdout") != "true":
            return False, "run.metrics_file 이나 run.metrics_stdout 필요"
    return True, f"cmd: {run['command'][:70]}"


def stage_preflight(card: dict) -> tuple[bool, list[str]]:
    run = card.get("run") or {}
    cwd = Path(run.get("cwd") or ROOT)
    cwd = cwd if cwd.is_absolute() else ROOT / cwd
    notes, ok = [], True
    for check in card.get("preflight") or []:
        m = re.match(r"^disk_mb\s*>=\s*(\d+)$", check)
        if m:
            free = disk_free_mb(cwd)
            good = free >= int(m.group(1))
            notes.append(f"disk {free}MB >= {m.group(1)}MB · {'OK' if good else 'FAIL'}")
            ok &= good
            continue
        m = re.match(r"^module:\s*([\w.]+)$", check)
        if m:
            py = run.get("python") or sys.executable
            r = subprocess.run([py, "-c", f"import {m.group(1)}"], capture_output=True, text=True)
            notes.append(f"module {m.group(1)} · {'OK' if r.returncode == 0 else 'FAIL'}")
            ok &= r.returncode == 0
            continue
        m = re.match(r"^path:\s*(.+)$", check)
        if m:
            p = Path(m.group(1))
            p = p if p.is_absolute() else (ROOT / p)
            good = p.exists()
            notes.append(f"path {m.group(1)} · {'OK' if good else 'FAIL'}")
            ok &= good
            continue
        notes.append(f"{check} · (알 수 없는 검사)")
    return ok, notes


def stage_execute(card: dict, execute: bool) -> tuple[bool, str, dict]:
    run = card.get("run") or {}
    if not execute:
        return True, "계획만 확인 (--execute 없음)", {}
    cwd = Path(run.get("cwd") or ROOT)
    cwd = cwd if cwd.is_absolute() else ROOT / cwd
    env = os.environ.copy()
    env.update({k: v for k, v in (run.get("env") or {}).items()})
    t0 = time.perf_counter()
    proc = subprocess.run(
        run["command"], shell=True, cwd=str(cwd), env=env,
        capture_output=True, text=True, timeout=int(run.get("timeout", 1800)),
    )
    wall = round(time.perf_counter() - t0, 1)
    tail = (proc.stdout or "").strip().splitlines()[-3:]
    ok = proc.returncode == 0
    return ok, f"exit={proc.returncode} · {wall}s · {tail[-1][:90] if tail else ''}", {
        "wall_seconds": wall, "exit": proc.returncode, "stdout_tail": tail,
        "stderr_tail": (proc.stderr or "").strip().splitlines()[-3:],
    }


def stage_judge(card: dict, meta: dict) -> tuple[bool, list[str], dict]:
    run = card.get("run") or {}
    raw = None
    if run.get("metrics_file"):
        p = Path(run["metrics_file"])
        p = p if p.is_absolute() else (ROOT / p)
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
    if raw is None and run.get("metrics_stdout") == "true":
        json_lines = [ln for ln in meta.get("stdout_tail", []) if ln.strip().startswith("{")]
        if json_lines:
            raw = json.loads(json_lines[-1])
    if raw is None:
        return False, ["지표를 찾지 못함"], {}

    metrics, results = {}, []
    for name, path in (card.get("metrics") or {}).items():
        try:
            metrics[name] = resolve(raw, str(path))
        except (KeyError, IndexError, ValueError) as exc:
            metrics[name] = f"missing({exc})"
    ok = True
    for rule in card.get("acceptance") or []:
        m = re.match(r"^(\w+)\s*(>=|<=|==|!=|>|<)\s*(.+)$", rule)
        if not m:
            results.append(f"{rule} · 형식 오류")
            ok = False
            continue
        name, op, want = m.groups()
        got = metrics.get(name)
        want_sym = want.strip()
        if want_sym in metrics:            # 지표끼리 비교: lewm_rank > nog_rank
            want = metrics[want_sym]
        try:
            want_v = float(want)
            good = {
                ">=": float(got) >= want_v, "<=": float(got) <= want_v,
                ">": float(got) > want_v, "<": float(got) < want_v,
                "==": float(got) == want_v, "!=": float(got) != want_v,
            }[op]
        except (TypeError, ValueError):
            good = False
        results.append(f"{name}={got} {op} {want} · {'PASS' if good else 'FAIL'}")
        ok &= good
    return ok, results, metrics


# --------------------------------------------------------------------------- #
def run_card(card_path: Path, execute: bool) -> int:
    card = load_card(card_path)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cid = str(card.get("id") or card_path.stem)
    manifest = {"id": cid, "card": str(card_path), "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    print(f"\n=== RRC · {cid} · {card.get('kind')} ===")
    ok, msg = stage_spec(card)
    print(f" 1 spec       {'OK ' if ok else 'FAIL'} {msg}")
    if not ok:
        manifest.update({"stage": "spec", "ok": False, "message": msg})
        (OUTDIR / f"{cid}.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        return 1

    ok, msg = stage_references(card)
    print(f" 2 references {'OK ' if ok else 'FAIL'} {msg}")
    if not ok:
        manifest.update({"stage": "references", "ok": False, "message": msg, "references": card.get("_refs")})
        (OUTDIR / f"{cid}.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        return 1

    ok, msg = stage_plan(card)
    print(f" 3 plan       {'OK ' if ok else 'FAIL'} {msg}")
    if not ok:
        manifest.update({"stage": "plan", "ok": False, "message": msg})
        (OUTDIR / f"{cid}.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        return 1

    ok, notes = stage_preflight(card)
    print(f" 4 preflight  {'OK ' if ok else 'FAIL'}")
    for note in notes:
        print(f"     · {note}")
    if not ok:
        manifest.update({"stage": "preflight", "ok": False, "checks": notes, "references": card.get("_refs")})
        (OUTDIR / f"{cid}.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        print("  → 실행 전 중단 (토큰 0)")
        return 1

    ok, msg, meta = stage_execute(card, execute)
    print(f" 5 execute    {'OK ' if ok else 'FAIL'} {msg}")
    if execute and not ok:
        manifest.update({"stage": "execute", "ok": False, "meta": meta, "references": card.get("_refs")})
        (OUTDIR / f"{cid}.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        return 1

    ok, results, metrics = stage_judge(card, meta)
    print(f" 6 judge      {'PASS' if ok else 'FAIL'}")
    for line in results:
        print(f"     · {line}")

    manifest.update({
        "stage": "judge", "ok": ok, "goal": card.get("goal"),
        "falsifier": card.get("falsifier"), "references": card.get("_refs"),
        "meta": meta, "metrics": metrics, "acceptance": results,
        "finishedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    })
    (OUTDIR / f"{cid}.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  → reports/requests/{cid}.json")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "run":
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(run_card(Path(sys.argv[2]), "--execute" in sys.argv))
