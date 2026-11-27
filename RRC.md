# 참고 요청 연산 (RRC) — 두 시스템을 한 층으로 통합

요청 하나를 받으면 **참고를 고정하고, 계획을 세우고, 실행 전에 가능 여부를 판정한 뒤에만** 계산에 들어간다. Fable 5.2 스터디 하네스와 LeWM 실험을 같은 코드로 돌린다.

```bash
python3 harness/request.py run requests/study-030-derived.yaml --execute
python3 harness/request.py run requests/lewm-collapse-v2.yaml --execute
```

## 6단계

| 단계 | 하는 일 | 실패하면 |
|---|---|---|
| 1 spec | 요청 카드 파싱, 합격 조건(실험은 반증 조건까지) 확인 | 실행 안 함 |
| 2 references | 참고 파일 sha256 고정 | 실행 안 함 |
| 3 plan | 실행 명령·지표 파일 확정 | 실행 안 함 |
| 4 preflight | 디스크·모듈·경로를 실제로 찔러봄 | **토큰 0으로 중단** |
| 5 execute | `--execute`일 때만 실행 | 매니페스트에 stderr 기록 |
| 6 judge | 지표 추출 → 합격/반증 대조 → `reports/requests/<id>.json` | exit 1 |

4단계가 핵심이다. 오늘 하루 막힌 네 가지(Claude 로그인, `coral.pth` 의존 사슬, `dsh` 경로, 중첩 샌드박스)는 모두 여기서 걸렸어야 했고, 전부 모델 호출 없이 판정 가능했다.

## 두 대상, 같은 코드

`kind`만 다르다. `study`는 스펙 적합도와 갤러리 재현성을, `experiment`는 가설과 반증 조건을 본다.

| 카드 | kind | 결과 |
|---|---|---|
| `study-030-derived` | study | **PASS** · delta `0.18` · composite `0.9747` · 파생판 1.00 |
| `lewm-collapse` | experiment | **FAIL** · rank 11.95 < 18.06 (1차 가설 기각) |
| `lewm-collapse-v2` | experiment | **PASS** · mean_std 0.0718 > 0.0222 · total_var 26.2 > 2.44 |

## 1차 실험이 남긴 것

1차 카드의 반증 조건은 "SIGReg를 끄면 effective rank가 무너진다"였다. 실제로는 반대였다 — rank는 11.95 → 18.06으로 **올라갔고**, 대신 분산 규모가 total_var 26.2 → 2.44로 10분의 1이 됐다. participation ratio는 활성 차원 수를 세지 분산의 크기를 보지 않기 때문이다.

그래서 1차는 **FAIL로 기록해 남기고**, 판정 기준을 분산으로 바꾼 2차 카드를 따로 만들었다. 1차를 지우고 2차만 남기면 사후 합리화가 되므로 둘 다 커밋한다.

## 실험 코드에서 고친 것

`lab/train_lib.py`의 `collect_embeddings`가 `jepa.encode`의 배치 규약(`b t ... -> (b t) ...`)을 어겼다. 프레임을 `(T,1,H,W)`로 넘겨 flatten 후 채널 40짜리 텐서가 들어갔다. `(1,T,1,H,W)`로 바꿔 고쳤고, 그대로 30초에 완주한다. 이 수정은 `lewm-study`(저장소 밖)에만 있다.

## 남은 한계

`references`는 지금 로컬 파일만 해시로 고정한다. URL 참고(논문·깃허브)는 사람이 받아 경로로 넣어야 한다. 다음 확장은 URL 수집 + 해시 고정이고, 그다음이 실패한 카드의 자동 수리(1차 FAIL → 2차 카드 자동 생성)다.
