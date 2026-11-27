# RSI 루프 — 원본은 그대로, 개선은 회귀로만 인정

이 저장소의 작업 규칙은 한 줄이다.

> **원본 76편과 프롬프트는 바이트 단위로 보존하고, 개선은 파생 경로에만 쓰며, "좋아졌다"는 말은 같은 명령의 전/후 수치로만 인정한다.**

## 1. 왜 이렇게 하는가

공급된 컬렉션(커밋 `369dae7`)은 이미 완성된 작품이다. 손대면 좋아지는 것처럼 보이지만 실제로는 조용히 나빠지는 경우가 대부분이라, 원본을 고치지 않고 **측정 → 파생 → 재측정**만 한다. 원본 불변은 약속이 아니라 테스트다.

```bash
python3 harness/manifest.py verify   # 241개 파일 sha256 재계산
```

## 2. 세 층의 검사 (희소 스케줄)

SpikingBrain(BICLab)의 **이벤트 구동 희소 활성 / 적응형 문턱** 구조를 검사 스케줄에 옮겼다. 참고 근거와 대응표는 [`refs/spikingbrain/NOTES.md`](refs/spikingbrain/NOTES.md).

| 층 | 무엇을 | 언제 |
|---|---|---|
| L1 체크섬 | 모든 입력 파일 해시 | 항상 (해시만, 초 단위) |
| L2 정적 적합성 | 팔레트·기법·키보드·접근성·자기완결성 | 파일이 바뀐 스터디만 |
| L3 브라우저 | 콘솔 오류·가로 넘침·스크린샷 | 크게 바뀐 스터디, 또는 하네스 자체가 바뀐 콜드 스타트 |

바뀌지 않은 스터디는 이전 판정을 재사용하고, `verified_unchanged`(안 바뀐 걸 확인함)와 `skipped`(건너뜀)를 **분리해서** 기록한다. "건너뛴 척"을 하지 않기 위해서다.

`harness/spiking.py`는 이 스케줄을 실제 LIF(leaky integrate-and-fire) 뉴런으로 돌린다. numpy만 쓰고 GPU·모델 가중치는 필요 없다.

```bash
python3 harness/spiking.py bench
# loops 12, neurons 76, dense_checks 912, spiking_checks 24
# sparsity 0.9737 (97.4%), coverage 1.0, missed_changes 0, max_delay_loops 0
```

## 3. 명령

```bash
python3 harness/regress.py --full --save-baseline   # 기준선 고정 (한 번)
python3 harness/regress.py                          # 이번 바퀴: 바뀐 것만
python3 harness/regress.py --full                   # 전체 스윕 (배포 전)
python3 harness/regress.py --scheduler sparse       # 해시 기반 단순 스케줄
node harness/runtime.mjs --only 030 --fps           # 한 편만 런타임 측정
```

회귀가 하나라도 있으면 **exit code 1**. 개선이 있어도 회귀가 있으면 실패다.

## 4. 지표 (기준선)

| 지표 | 값 | 의미 |
|---|---|---|
| `originals` | 241/241 byte-identical | 원본 불변 |
| `static.composite_mean` | 0.9747 | 스펙 적합도 평균 (팔레트 45% + 기법 35% + 접근성 20%) |
| `static.palette_perfect` | 74/76 | 프롬프트가 지정한 hex를 전부 쓰는 작품 수 |
| `static.gallery_passed` | 13/13 | 갤러리 정합성 (카드·프롬프트 원문·썸네일·alt·id·lang) |
| `static.reimpl_mean_delta` | **+0.18** | 파생판 − 원본 (030 한 편) |
| `runtime.failed` | 0 | 캡처 실패 |
| `runtime.console_errors` | 0 | 콘솔 오류가 있는 페이지 수 |
| `runtime.mobile_overflow` | 0 | 360px에서 가로로 넘치는 페이지 수 |

## 5. 이번 바퀴에서 실제로 바뀐 것

| 변경 | 근거 | 회귀 |
|---|---|---|
| 갤러리에 **Interaction model · Visual techniques** 표시 | `build_gallery.py`가 4개 섹션만 잘라 `INTERACTION MODEL`을 기법에 섞어버리고 표시하지 않던 버그 | 갤러리 검사 11/13 → 13/13 |
| **Skip link** 추가 | 키보드 사용자가 76개 카드를 지나쳐야 했음 | 접근성 지표 |
| `studies/030-rose-window/` 파생판 | 원본이 자기 프롬프트의 hex 4개(ruby·cobalt·emerald·amethyst)를 안 쓰고 키보드 계약도 없음 | 스펙 점수 0.82 → 1.00 |
| 키보드 측정 수정 | `keydown` 유무로 재던 지표는 네이티브 포커스 가능 컨트롤(76/76편이 보유)을 놓쳤다 → `focusable`/`operable`로 교체 | 오탐 8건 → 0건 |

## 6. 미해결 (숨기지 않음)

- 파생판은 1편(030)뿐이다. 나머지 75편은 아직 원본 그대로다.
- 030 파생판도 원본의 유리 밀도·석재 조형 디테일에 못 미친다. 점수는 높지만 눈으로는 아직 원본이 더 낫다.
- FPS 측정은 기본 꺼짐(`--fps`). 헤드리스에서 동시 실행 시 페이지 간 간섭으로 값이 0~61로 튀어 신뢰할 수 없다.
- SpikingBrain-7B **가중치 추론은 이 기기에서 실행하지 않았다.** 이유는 "GPU 전용"이 아니라 실측이다: 이 맥은 RAM 8GB, 데이터 볼륨 여유 2.5GB인데 7B bf16 가중치는 14GB급이고 업스트림은 GGUF/CPU 양자화 배포판을 내지 않는다. 돌린 것은 스파이크 연산 자체(`harness/spiking.py`, numpy LIF)와 그 희소성 수치다. 가중치까지 돌리려면 여유 디스크 ≥ 20GB + RAM ≥ 16GB, 또는 vLLM/MetaX 경로가 필요하다.
