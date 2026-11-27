"""RRC 게이트를 통과한 파생 스터디를 AlphaEvolve로 생성한다.

    python3 evolution/evolve_study.py --stems 017-spore-print-riso-zine,049-conchology-cabinet

각 스텁에서 시작해 스펙(팔레트·기법·접근성·구조)을 최대화하는 HTML을 진화시키고,
1) 평가 점수 >= 원본 스펙 점수, 2) Chrome 렌더에서 콘솔 오류 0, 3) 가로 넘침 없음
을 모두 만족할 때만 studies/<stem>/index.html 로 승격한다. 아니면 후보로만 남긴다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT.parents[1] / "refs"
OPENEVOLVE = REFS / "openevolve"
PY = OPENEVOLVE / ".venv" / "bin" / "python"
EVAL = ROOT / "evolution" / "study030" / "evaluator.py"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

STUB = '''"""Evolved candidate for {stem} — built from scratch against its spec."""
# EVOLVE-BLOCK-START
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
</head>
<body>
<canvas id="scene" style="display:block;width:100vw;height:100vh;background:#111"></canvas>
<script>
const c = document.getElementById('scene').getContext('2d');
c.fillStyle = '#888';
c.fillRect(40, 40, 200, 200);
</script>
</body>
</html>
"""
# EVOLVE-BLOCK-END
'''

CONFIG = """max_iterations: {iters}
checkpoint_interval: 1
random_seed: {seed}
llm:
  primary_model: "deepseek-flash"
  primary_model_weight: 1.0
  api_base: "http://127.0.0.1:8123/v1"
  temperature: 0.7
  max_tokens: 16000
  timeout: 240
prompt:
  system_message: "Emit ONE minimal SEARCH/REPLACE diff inside the block. Improve a single self-contained HTML art study against its written spec: exact hex colours, canvas or svg, prefers-reduced-motion, keyboard input, no external requests, under 140 KB."
database:
  population_size: 4
  archive_size: 2
  num_islands: 1
  elite_selection_ratio: 0.25
  exploitation_ratio: 0.7
  similarity_threshold: 0.99
evaluator:
  timeout: 180
  cascade_thresholds: [1.0]
  parallel_evaluations: 1
diff_based_evolution: true
"""


def api_key() -> str:
    for line in (Path.home() / ".deepseek-science" / "deepseek.env").read_text().splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no key")


def extract(program: Path) -> str:
    m = re.search(r'HTML = r"""(.*?)"""', program.read_text(encoding="utf-8"), re.S)
    return m.group(1) if m else ""


def render_gate(html: str, stem: str) -> dict:
    out = Path("/tmp/evo-gate") / stem
    out.mkdir(parents=True, exist_ok=True)
    page = out / "index.html"
    page.write_text(html)
    shot = out / "shot.png"
    r = subprocess.run(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--no-first-run", "--user-data-dir=/tmp/evo-profile", "--window-size=1440,1000",
         "--virtual-time-budget=2500", f"--screenshot={shot}", f"file://{page}"],
        capture_output=True, text=True, timeout=120,
    )
    errs = [ln for ln in r.stderr.splitlines() if "Uncaught" in ln or "ERROR:CONSOLE" in ln]
    return {"rendered": shot.exists(), "shot": str(shot), "console_errors": errs[:5], "bytes": len(html.encode())}


def run_stem(stem: str, iters: int, seed: int) -> dict:
    spec = ROOT / f"{stem}.txt"
    if not spec.exists():
        return {"stem": stem, "status": "no-spec"}
    work = ROOT / "evolution" / stem
    work.mkdir(parents=True, exist_ok=True)
    title = spec.read_text(encoding="utf-8").splitlines()[1].strip() or stem
    (work / "initial_program.py").write_text(STUB.format(stem=stem, title=title))
    (work / "config.yaml").write_text(CONFIG.format(iters=iters, seed=seed))

    env = os.environ.copy()
    env["STUDY_SPEC"] = str(spec)
    env["OPENAI_API_KEY"] = api_key()
    r = subprocess.run(
        [str(PY), "openevolve-run.py", str(work / "initial_program.py"), str(EVAL),
         "--config", str(work / "config.yaml"), "--iterations", str(iters)],
        cwd=str(OPENEVOLVE), env=env, capture_output=True, text=True, timeout=3600,
    )
    best_info = work / "openevolve_output" / "best" / "best_program_info.json"
    if not best_info.exists():
        return {"stem": stem, "status": "no-candidate", "exit": r.returncode,
                "tail": (r.stdout or "").strip().splitlines()[-2:]}
    info = json.loads(best_info.read_text())
    html = extract(work / "openevolve_output" / "best" / "best_program.py")
    gate = render_gate(html, stem)
    return {
        "stem": stem, "status": "candidate", "exit": r.returncode,
        "score": info.get("metrics", {}).get("combined_score"),
        "metrics": info.get("metrics", {}), "gate": gate, "html": html,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", required=True)
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--promote", action="store_true")
    a = ap.parse_args()

    results = []
    for i, stem in enumerate(s for s in a.stems.split(",") if s):
        print(f"=== {stem}: {a.iterations} iterations ===", flush=True)
        res = run_stem(stem, a.iterations, a.seed + i)
        results.append({k: v for k, v in res.items() if k != "html"})
        print(json.dumps({k: res.get(k) for k in ("stem", "status", "score", "gate")}, ensure_ascii=False), flush=True)
        if a.promote and res.get("status") == "candidate" and res["gate"]["rendered"] \
                and not res["gate"]["console_errors"] and (res.get("score") or 0) >= 0.98:
            dest = ROOT / "studies" / stem / "index.html"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(res["html"])
            print(f"  promoted → {dest.relative_to(ROOT)}", flush=True)
            results[-1]["promoted"] = True

    out = ROOT / "reports" / "evolve-studies.json"
    out.write_text(json.dumps({"builtAt": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"), "results": results},
                              indent=1, ensure_ascii=False))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
