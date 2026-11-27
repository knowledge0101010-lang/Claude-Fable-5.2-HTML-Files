"""Train one LeWM variant for the AlphaEvolve evaluator (runs under the torch python).

    <conda-python> train_probe.py --lambda 0.09 --steps 30 --out /tmp/probe.json

Writes the collapse metrics as JSON so the evaluator (a different interpreter)
never has to import torch.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path("/Users/gojunjang/Documents/deepseek-harness/default-workspace/lewm-study")
sys.path.insert(0, str(LAB / "lab"))
sys.path.insert(0, str(LAB / "pylibs"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lambda", dest="lam", type=float, required=True)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import numpy as np
    import train_lib as T

    d = np.load(LAB / "lab" / "data.npz")
    frames = d["frames"].astype(np.float32) / 255.0
    actions = d["actions"].astype(np.float32)
    n_train = int(0.9 * frames.shape[0])

    model, info = T.train_variant("probe", a.lam, frames, actions, n_train, steps=a.steps, log_every=10_000)
    Z = T.collect_embeddings(model, frames[n_train:], actions[n_train:], frames.shape[0] - n_train)
    cm = T.collapse_metrics(Z)
    Path(a.out).write_text(json.dumps({"lambda": a.lam, "steps": a.steps, "collapse": cm}, indent=1))
    print(json.dumps(cm))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
