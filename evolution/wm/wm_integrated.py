"""Percepta-WM × LeWM 통합 프로토타입.

무엇을 합쳤나
  LeWM   : 코드 수준에서 확보(jepa.py / module.py). 잠재 전이 = ARPredictor + SIGReg.
  Percepta: 공개 초록 수준에서만 확보("perception-driven world-model for agent-based
            simulation"). 따라서 그 층은 규격(부분 관측 → 개별 정책 → 제도 제약 → 거시 상태)
            으로 재구성했다. 코드를 가져온 것이 아님을 명시한다.

빠르게 연산
  잠재 전이는 LeWM predictor 한 번, 에이전트 인지·정책은 순수 텐서 연산으로 배치화했다.
  N명 에이전트를 for-loop 없이 (N, D) 행렬 곱으로 처리하고, 측정값을 출력한다.

    <torch-python> wm_integrated.py --agents 1000 --steps 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB / "lab"))
sys.path.insert(0, str(LAB / "pylibs"))
sys.path.insert(0, str(LAB / "le-wm"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

import model as LM  # noqa: E402

DEV = "mps" if torch.backends.mps.is_available() else "cpu"


class PerceptaLayer:
    """부분 관측 + 개별 정책 + 제도 제약. LeWM 잠재를 관측 공간으로 쓴다."""

    def __init__(self, n_agents: int, dim: int, act_dim: int = 2, keep: float = 0.35, seed: int = 0):
        g = torch.Generator(device="cpu").manual_seed(seed)
        mask = (torch.rand(n_agents, dim, generator=g) < keep).float()
        self.mask = mask.to(DEV)
        self.policy = (torch.randn(n_agents, act_dim, dim, generator=g) * 0.35).to(DEV)
        # 제도 제약: 총 행동량 상한 (Percepta의 제도·거시 규칙 자리)
        self.cap = 0.6

    @torch.no_grad()
    def act(self, z: torch.Tensor) -> torch.Tensor:
        """z: (B, D) 현재 잠재 → 집계 행동 (B, act_dim)."""
        obs = z.unsqueeze(1) * self.mask.unsqueeze(0)          # (B,N,D)
        intents = torch.einsum("bnk,nak->bna", obs, self.policy)  # (B,N,A)
        agg = intents.mean(dim=1)                              # (B,A)
        norm = agg.norm(dim=-1, keepdim=True).clamp(min=1e-6)
        scale = torch.clamp(self.cap / norm, max=1.0)           # 제도 상한
        return agg * scale


def bench(agents: int, steps: int, batch: int, train_steps: int = 0) -> dict:
    mdl = LM.build_model().to(DEV)
    ckpt = LAB / "lab" / "runs" / "lewm.pt"
    if ckpt.exists():
        try:
            mdl.load_state_dict(torch.load(ckpt, map_location=DEV))
        except RuntimeError:
            pass
    mdl.eval()
    perc = PerceptaLayer(agents, LM.EMB if hasattr(LM, "EMB") else 32)

    g = torch.Generator(device="cpu").manual_seed(1)
    z = torch.randn(batch, 3, 32, generator=g).to(DEV)      # (B,T,D) 잠재 이력
    warm = 5
    t0 = time.perf_counter()
    for _ in range(warm):
        a = perc.act(z[:, -1])
        # jepa.predict needs emb (B,T,D) and act_emb (B,T,A_emb) with the same T;
        # the rollout repeats the newest action across the history window.
        act_emb = mdl.action_encoder(a.unsqueeze(1)).expand(-1, z.size(1), -1)
        nxt = mdl.predict(z, act_emb)[:, -1:]
        z = torch.cat([z[:, 1:], nxt], dim=1)
    if DEV == "mps":
        torch.mps.synchronize()
    t_warm = time.perf_counter() - t0

    z = torch.randn(batch, 3, 32, generator=g).to(DEV)
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(steps):
            a = perc.act(z[:, -1])
            act_emb = mdl.action_encoder(a.unsqueeze(1)).expand(-1, z.size(1), -1)
            z = torch.cat([z[:, 1:], mdl.predict(z, act_emb)[:, -1:]], dim=1)
    if DEV == "mps":
        torch.mps.synchronize()
    wall = time.perf_counter() - t0

    latency = wall / steps
    return {
        "device": DEV,
        "agents": agents,
        "batch": batch,
        "steps": steps,
        "wall_seconds": round(wall, 3),
        "ms_per_world_step": round(latency * 1000, 3),
        "world_steps_per_sec": round(steps / wall, 1),
        "agent_updates_per_sec": round(steps * agents / wall, 0),
        "predict_calls_per_sec": round(steps / wall, 1),
        "lifelong_equivalent_agent_steps": steps * agents,
        "warmup_seconds": round(t_warm, 3),
        "params": sum(p.numel() for p in mdl.parameters()),
        "checkpoint_loaded": ckpt.exists(),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, default=1000)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--out", default=str(LAB / "lab" / "runs" / "wm_integrated.json"))
    a = ap.parse_args()
    res = bench(a.agents, a.steps, a.batch)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
