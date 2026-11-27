# Percepta WM × LeWM 역설계 · 통합 (실행본)

## 근거 수준을 먼저 밝힌다

| 대상 | 확보한 것 | 수준 |
|---|---|---|
| LeWM (LeWorldModel) | `le-wm/jepa.py`, `module.py` 실제 소스 | **코드 수준** 역설계 |
| Percepta WM | 공개 초록(SSRN 6211649) "perception-driven world-model for agent-based simulation" | **규격 수준** 재구성 |

즉 이 통합은 "LeWM의 잠재 동역학" 위에 "Percepta식 인지·제도 층"을 규격대로 얹은 것이고,
Percepta 쪽 코드를 복제한 것이 아니다. 그 구분을 코드 주석에도 남겼다.

## 통합 구조

```
Percepta 층                        LeWM 층
부분 관측(마스크 35%)  ──┐
개별 정책(선형, N명)   ──┼─→ 집계 행동 ─→ action_encoder → ARPredictor
제도 제약(총량 상한)   ──┘                     ↑
                                     잠재 이력 (B,T,D)=(B,3,32)
```

- 에이전트 N명을 for-loop 없이 `einsum("bnk,nak->bna", obs, policy)`로 배치 처리
- 제도 제약은 집계 행동의 노름 상한(`cap=0.6`)으로 구현 — Percepta의 거시 규칙 자리
- 잠재 전이는 LeWM predictor 1회, 궤적은 이력 3스텝 유지

## 측정 (Apple M2, MPS, 배치 32)

| 지표 | 값 |
|---|---|
| 파라미터 | 833,574 |
| 월드 스텝당 | **2.521 ms** |
| 월드 스텝/초 | **396.7** |
| 에이전트 업데이트/초 | **396,671** |
| 200 스텝 실행 | 0.504 s (워밍업 0.272 s) |
| 체크포인트 | `lab/runs/lewm.pt` 로드 |

1000명 에이전트 × 200 스텝 = 20만 에이전트-스텝을 0.5초에 처리했다.

## 고친 것 (계약)

`jepa.predict(emb, act_emb)`는 **같은 T**를 요구한다. 처음엔 `(B,1,A_emb)`를 넣어
`pos_embedding` 크기 불일치로 죽었다. 롤아웃에서는 최신 행동을 이력 길이만큼 확장해 넘긴다.
`action_encoder`는 `(B,T,A)`를 받으므로 `a.unsqueeze(1)`이 필요하다.

## 한계

- Percepta 층은 논문 초록 기반이라 실제 프레임워크의 자산·규칙 엔진과 다를 수 있다.
- 정책은 학습되지 않은 선형 맵이다(속도 측정용). 논문 재현이 아니라 **연산 경로 검증**이다.
- 다음 단계: Percepta의 실제 스키마(에이전트 속성·제도 규칙 DSL)를 확보하면 그 자리에 꽂는다.
