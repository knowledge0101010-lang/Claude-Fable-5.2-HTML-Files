"""통합 AlphaEvolve 실행 — 두 대상을 한 번에 진화시킨다.

    python3 evolution/run_integrated.py [--iterations-a 3] [--iterations-b 2]

A. study030   : 스펙만 주고 HTML을 처음부터 진화 (채점 = harness/spec.py + 구조 게이트)
B. lewm       : LeWM ablation 프로토콜을 진화 (채점 = SIGReg on/off의 분산 분리)

각 대상은 openevolve를 따로 돌리지만, 드라이버가 한 번에 실행하고 결과를 한 표로 합친다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # fable52/work
REFS = ROOT.parents[1] / "refs"                      # default-workspace/refs
OPENEVOLVE = REFS / "openevolve"
PY = OPENEVOLVE / ".venv" / "bin" / "python"
KEY_FILE = Path.home() / ".deepseek-science" / "deepseek.env"

TASKS = {
    "study030": {
        "program": ROOT / "evolution" / "study030" / "initial_program.py",
        "evaluator": ROOT / "evolution" / "study030" / "evaluator.py",
        "config": ROOT / "evolution" / "config-study030.yaml",
        "iters": 3,
    },
    "lewm": {
        "program": ROOT / "evolution" / "lewm" / "initial_program.py",
        "evaluator": ROOT / "evolution" / "lewm" / "evaluator.py",
        "config": ROOT / "evolution" / "config-lewm.yaml",
        "iters": 2,
    },
}


def api_key() -> str:
    for line in KEY_FILE.read_text().splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DEEPSEEK_API_KEY 없음")


def run_task(name: str, iters: int, key: str) -> dict:
    cfg = TASKS[name]
    t0 = time.perf_counter()
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = key
    r = subprocess.run(
        [str(PY), "openevolve-run.py", str(cfg["program"]), str(cfg["evaluator"]),
         "--config", str(cfg["config"]), "--iterations", str(iters)],
        cwd=str(OPENEVOLVE), env=env, capture_output=True, text=True, timeout=3600,
    )
    wall = round(time.perf_counter() - t0, 1)
    out_dir = cfg["program"].parent / "openevolve_output" / "best"
    info = out_dir / "best_program_info.json"
    best = json.loads(info.read_text()) if info.exists() else {}
    tail = [ln for ln in (r.stdout or "").strip().splitlines() if ln.strip()][-3:]
    return {
        "task": name, "exit": r.returncode, "wall_seconds": wall,
        "best_score": best.get("metrics", {}).get("combined_score"),
        "best_metrics": best.get("metrics", {}),
        "best_file": str(info) if info.exists() else None,
        "tail": tail,
        "stderr_tail": (r.stderr or "").strip().splitlines()[-2:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations-a", type=int, default=3)
    ap.add_argument("--iterations-b", type=int, default=2)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    key = api_key()

    plan = []
    if "study030" in TASKS and (not a.only or "study030" in a.only):
        plan.append(("study030", a.iterations_a))
    if "lewm" in TASKS and (not a.only or "lewm" in a.only):
        plan.append(("lewm", a.iterations_b))

    results = []
    for name, iters in plan:
        print(f"=== {name}: {iters} iterations ===", flush=True)
        res = run_task(name, iters, key)
        print(json.dumps({k: res[k] for k in ("task", "exit", "wall_seconds", "best_score")}, ensure_ascii=False), flush=True)
        results.append(res)

    out = ROOT / "reports" / "evolution-integrated.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"builtAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "results": results}, indent=1, ensure_ascii=False))
    print(f"\nwrote {out}")
    for r in results:
        print(f"  {r['task']:10s} best={r['best_score']}  {r['wall_seconds']}s  exit={r['exit']}")
    return 0 if all(r["exit"] == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
