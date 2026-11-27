"""작업 인계(handoff) — 한 번의 요청을 다음 세션이 이어받을 수 있게 남긴다.

오래된 'Science Workbench Suite'가 쓰던 세 파일 구성을 그대로 가져왔다:
`research-handoff.json`(상태·다음 행동), `research-run.json`(타임라인),
`research-notebook.md`(사람이 읽는 기록). 우리 RRC 카드 실행이 끝나면 자동으로
`reports/handoffs/<id>/`에 이 셋을 남긴다.

    from handoff import write_handoff
    write_handoff(card, manifest)      # request.py 가 judge 단계 뒤에 호출
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFFS = ROOT / "reports" / "handoffs"


def _next_actions(card: dict, manifest: dict) -> list[str]:
    """판정 결과에서 다음 행동을 기계적으로 뽑는다."""
    actions: list[str] = []
    if not manifest.get("ok"):
        stage = manifest.get("stage")
        if stage == "preflight":
            actions.append("preflight 실패 항목을 해결한 뒤 같은 카드를 재실행")
        elif stage == "execute":
            tail = (manifest.get("meta", {}).get("stderr_tail") or [""])[-1]
            actions.append(f"실행 실패 원인 수정: {tail[:160]}")
        elif stage == "judge":
            failed = [r for r in manifest.get("acceptance", []) if "FAIL" in r]
            actions.append("합격 조건 재검토 또는 카드 기준 수정: " + "; ".join(failed[:3]))
        else:
            actions.append(f"{stage} 단계 오류 확인")
    else:
        actions.append("판정 통과 — 결과를 승격할지 결정 (studies/ 또는 리포트)")
        if card.get("kind") == "experiment":
            actions.append("같은 조건으로 반복 실행해 분산 확인 (noise band)")
    if (card.get("run") or {}).get("metrics_file"):
        actions.append("지표 파일의 원본을 보관 (참고 해시와 함께)")
    return actions


def write_handoff(card: dict, manifest: dict) -> Path:
    cid = str(card.get("id") or "run")
    out = HANDOFFS / cid
    out.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    handoff = {
        "id": cid,
        "kind": card.get("kind"),
        "goal": card.get("goal"),
        "falsifier": card.get("falsifier"),
        "verdict": "PASS" if manifest.get("ok") else "FAIL",
        "stage_reached": manifest.get("stage"),
        "metrics": manifest.get("metrics", {}),
        "references": manifest.get("references", []),
        "card": str(card.get("_card_path", "")),
        "evidence": {
            "acceptance": manifest.get("acceptance", []),
            "checks": manifest.get("checks", []),
            "meta": manifest.get("meta", {}),
        },
        "next_actions": _next_actions(card, manifest),
        "writtenAt": now,
    }
    (out / "research-handoff.json").write_text(json.dumps(handoff, indent=1, ensure_ascii=False), encoding="utf-8")

    run = {
        "id": cid,
        "timeline": [
            {"at": manifest.get("startedAt"), "event": "start"},
            {"at": now, "event": f"stage:{manifest.get('stage')}", "verdict": handoff["verdict"]},
        ],
        "wall_seconds": (manifest.get("meta") or {}).get("wall_seconds"),
        "exit": (manifest.get("meta") or {}).get("exit"),
        "stdout_tail": (manifest.get("meta") or {}).get("stdout_tail"),
    }
    (out / "research-run.json").write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")

    md = [
        f"# {cid} — {handoff['verdict']}",
        "",
        f"- 종류: {card.get('kind')}",
        f"- 목표: {card.get('goal')}",
    ]
    if card.get("falsifier"):
        md.append(f"- 반증 조건: {card['falsifier']}")
    md += ["", "## 참고 (해시 고정)", ""]
    for ref in manifest.get("references", []):
        md.append(f"- `{ref.get('ref')}` — {ref.get('sha256', ref.get('status'))}")
    md += ["", "## 판정", ""]
    md += [f"- {line}" for line in manifest.get("acceptance", []) or ["(판정 전 중단)"]]
    md += ["", "## 지표", ""]
    for k, v in (manifest.get("metrics") or {}).items():
        md.append(f"- `{k}` = {v}")
    md += ["", "## 다음 행동", ""]
    md += [f"{i+1}. {a}" for i, a in enumerate(handoff["next_actions"])]
    (out / "research-notebook.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out
