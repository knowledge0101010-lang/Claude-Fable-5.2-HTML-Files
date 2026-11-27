"""Evaluator for the integrated AlphaEvolve run — target B: the LeWM ablation."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = "/opt/homebrew/Caskroom/miniconda/base/bin/python3"
PROBE = ROOT / "evolution" / "lewm" / "train_probe.py"


def params(program_path: str) -> dict:
    ns: dict = {}
    exec(Path(program_path).read_text(encoding="utf-8"), ns)
    return dict(ns.get("PARAMS") or {})


def probe(lam: float, steps: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        out = Path(fh.name)
    r = subprocess.run(
        [PY, str(PROBE), "--lambda", str(lam), "--steps", str(steps), "--out", str(out)],
        capture_output=True, text=True, timeout=900,
    )
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout).strip().splitlines()[-1][:200]}
    return json.loads(out.read_text())


def evaluate(program_path: str) -> dict:
    p = params(program_path)
    lam = float(p.get("lam", 0.09))
    steps = max(10, min(60, int(p.get("steps", 30))))
    treated = probe(lam, steps)
    control = probe(0.0, steps)
    if "error" in treated or "error" in control:
        return {"combined_score": 0.0, "error": treated.get("error") or control.get("error")}

    t, c = treated["collapse"], control["collapse"]
    sep_std = t["mean_std"] - c["mean_std"]
    sep_var = t["total_var"] - c["total_var"]
    # variance separation is the signal the paper's ablation is really about
    score = max(0.0, min(1.0, sep_std * 10.0 + sep_var / 50.0))
    return {
        "combined_score": round(score, 4),
        "sep_std": round(sep_std, 5),
        "sep_var": round(sep_var, 3),
        "treated": {"lam": lam, "mean_std": t["mean_std"], "total_var": t["total_var"], "eff_rank": t["eff_rank"]},
        "control": {"lam": 0.0, "mean_std": c["mean_std"], "total_var": c["total_var"], "eff_rank": c["eff_rank"]},
        "steps": steps,
    }
