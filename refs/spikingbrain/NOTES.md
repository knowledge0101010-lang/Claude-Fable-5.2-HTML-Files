# Reference: SpikingBrain (BICLab) — 참고 메모

> 목적: 이 프로젝트(Fable 5.2 HTML 컬렉션의 자기개선 회귀 루프)에 **무엇을** 가져올지 근거와 함께 고정한다.
> 원본 모델을 재현하는 것이 아니라, 구조 아이디어만 하네스 설계에 옮긴다.

## 출처

| 항목 | 위치 |
|---|---|
| GitHub (7B) | https://github.com/BICLab/SpikingBrain-7B |
| GitHub (2.0) | https://github.com/BICLab/SpikingBrain2.0 |
| arXiv 1.0 | https://arxiv.org/abs/2509.05276 |
| 기술보고서 | 레포 내 `SpikingBrain_Report_Eng.pdf` |
| 가중치 | ModelScope (`Panyuqi/V1-7B-base`, `-sft-s3-reasoning`, W8ASpike) |

확인한 사실 (README, 2026-11-26):

- **구성**: hybrid efficient attention(선형 + 하이브리드 선형) + MoE + **spike encoding**. 7B(선형) / 76B(하이브리드 선형 MoE).
- **데이터 효율**: 범용 변환 파이프라인으로 continual pre-training을 **데이터 2% 미만**으로 수행.
- **길이**: 4M 토큰에서 TTFT **100× 이상** 단축.
- **희소성**: 마이크로 수준 spike **69.15% sparsity**, 매크로 수준 MoE 희소성과 결합. → 뉴로모픽 칩 설계 지침.
- **이식성**: MetaX(NVIDIA 외) 클러스터용 연산자·병렬·통신 재작성, vLLM 플러그인(vllm-hymeta), W8ASpike 양자화.
- **정직한 한계**: W8ASpike는 **pseudo-spiking**(텐서 근사)이며 진짜 비동기 이벤트 구동은 뉴로모픽 하드웨어 범위 밖이라고 스스로 명시.

## 이 프로젝트에 옮기는 것 (설계 대응표)

| SpikingBrain 원리 | 회귀 하네스에서의 대응 | 구현 위치 |
|---|---|---|
| 이벤트 구동 희소 활성 (69.15%) | 전체 76개를 매번 훑지 않고 **내용 해시가 바뀐 스터디만** 검사. 나머지는 캐시된 판정 재사용 | `harness/sparse.py` |
| 적응형 스파이크 뉴런 (문턱값) | 검사 등급 L1(해시)→L2(정적 적합성)→L3(브라우저 실행). **직전 대비 변화량이 문턱을 넘을 때만** 상위 등급으로 승격 | `harness/regress.py --plan` |
| 하이브리드 어텐션 (전역+국소) | 전역 검사(원본 불변·갤러리 정합)는 항상, 국소 검사(개별 스터디 런타임)는 변경분만 | `harness/regress.py` |
| 2% 데이터로 continual pre-training | 기준선(`reports/baseline.json`)을 재측정 없이 재사용하는 **증분 갱신** | `reports/` |
| 100× TTFT (긴 문맥) | 한 바퀴 소요 시간을 지표로 기록. 희소 모드의 실제 단축률을 수치로 남김 | `reports/latest.json → loop.wall_seconds` |
| pseudo vs true spiking 구분 | 하네스도 **"정말 건너뛰었는지"와 "건너뛴 척했는지"를 구분**해 기록 | `skipped[]` + `verified_unchanged[]` |
| 크로스 플랫폼 이식 | 하네스는 npm 의존성 0 (Node 22 내장 fetch/WebSocket + Python 표준+PIL) | `harness/runtime.mjs` |

## 하지 않는 것

- 모델 가중치 다운로드·추론 없음 (수 GB, 이 루프의 목적과 무관).
- 뉴로모픽 하드웨어/SNN 프레임워크 도입 없음. 우리가 쓰는 것은 **검사 스케줄링** 개념뿐.
- SpikingBrain 코드 복사 없음. 아이디어 매핑만.

## 참고 문헌 (본문 인용)

- SpikingBrain Technical Report (TMLR 2026): https://arxiv.org/abs/2509.05276
- SpikingBrain2.0: https://github.com/BICLab/SpikingBrain2.0
- Int2Spike (pseudo-spiking 인터페이스): https://github.com/BICLab/Int2Spike
