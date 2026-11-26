# Fable 5.0 → 5.2 델타 (측정값)

"페이블 5.2를 구현한다"의 첫 단계는 **어느 파일이 5.2인지 못 박는 것**이다. 이 문서는 그 고정 결과와 5.0 대비 실제 차이다.

## 1. 출처와 지문 (2026-11-26 수집)

| 파일 | 크기 | sha256(앞 12) | 출처 |
|---|---|---|---|
| `web-app-fable-5.2.md` | 426,203자 / 2,292줄 | `f6c62d2bdf18` | [CL4R1T4S / ANTHROPIC / CLAUDE-WEB-APP-FABLE-5.2.md](https://github.com/elder-plinius/CL4R1T4S/blob/main/ANTHROPIC/CLAUDE-WEB-APP-FABLE-5.2.md) |
| `claude-code-fable-5.2.txt` | 957,315자 / 7,832줄 | `d54e74e3ffd3` | [CL4R1T4S / ANTHROPIC / CLAUDE-CODE-FABLE-5.2.txt](https://github.com/elder-plinius/CL4R1T4S/blob/main/ANTHROPIC/CLAUDE-CODE-FABLE-5.2.txt) |
| `official-release-notes-5.2.md` | 31,621자 | `93893c2262e5` | [asgeirtj/system_prompts_leaks 2026-11-09](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/official/2026-11-09-claude-fable-5.2.md) — Anthropic 공식 릴리스노트 전재 |
| `official-release-notes-5.2.kalaris.md` | 32,895자 | `8a8c34a308a0` | [KalarisLabs/claude-systems-prompts](https://github.com/KalarisLabs/claude-systems-prompts) (같은 원문, 메타 헤더 포함) |
| `fable-5.0-local-copy.md` | 122,428자 | `1ef1257c67eb` | 로컬 `~/.claude/CLAUDE-FABLE-5.md` 사본. CL4R1T4S의 `CLAUDE-FABLE-5.md`와 **바이트 동일** 확인 |

두 공식 릴리스노트 사본은 XML 태그를 마크다운 제목으로 바꾼 것만 다르고 내용이 같다(유사도 0.9868). 즉 공식 5.2 텍스트는 31 KB뿐이고, 그 안에 **도구 정의·메모리·아티팩트·커넥터가 없다.**

```bash
python3 harness/prompt_pack.py verify   # 5개 파일 해시 고정 확인
```

## 2. 5.0 → 5.2 구조 변화 (측정)

| | 5.0 (로컬) | 5.2 (웹앱 전체) |
|---|---|---|
| 문자 수 | 122,428 | 426,203 (**3.48×**) |
| 추정 토큰 | 34,000 | 118,400 |
| 도구 정의 | 15개 (마크다운 표) | **67개 `<function>`** (`mcp__claude_ai__*`, `mcp__memory__*` 포함) |
| 섹션 | 73 | 174 (추가 101, 삭제 52) |

5.2에서 새로 생긴 축은 대부분 **에이전트 동작**이다: `<agentic_behavior>`, `<workspace_and_tools>`(workspace·where_files_live·device_bridge·delivering_files), `<artifacts>`, `<skills>`, `<connectors>`, `<browsers>`, `<desktop_computer_use>`, `<questions_and_task_list>`, `<scheduled_tasks>`, `<how_a_task_runs>`(starting·working_unattended·keeping_the_person_informed·building·finishing). 거절 처리에는 실제 대화 예시(`<example>`+`<rationale>`)가 붙고, 사이버 거절(`<cyber_refusal_handling>`)과 `<mythos_info>`(Mythos 티어·Fable과의 차이)가 추가됐다. 5.0에 있던 `<memory_system>`·`<persistent_storage_for_artifacts>`는 5.2에서 `<memory_application_instructions>`·아티팩트 규칙으로 재편됐다.

## 3. 런타임 등급 (무엇을 system 메시지에 넣을 것인가)

전체 426 KB를 그대로 넣으면 118K 토큰이다. 128K 문맥에서는 대화 한두 턴이면 끝난다. 그래서 등급을 나눠 쓴다.

| 등급 | 내용 | 크기 | 추정 토큰 | 용도 |
|---|---|---|---|---|
| 계약 | `FABLE5-CONTRACT.md` | 864자 | 240 | 매 요청 저비용 |
| 행동 코어 | `<functions>` 이전까지 | 152,693자 | 42,400 | 품질 우선 단일 호출 |
| 전체 | 웹앱 5.2 전문 | 426,203자 | 118,400 | 장문맥 모델 전용 |
| 코드 | Claude Code 5.2 전문 | 957,315자 | 266,000 | 128K 문맥에 안 들어감 → 분할 주입 필수 |

```bash
python3 harness/prompt_pack.py build \
  --behavior refs/prompts/fable-5.2/web-app-fable-5.2.md \
  --out reports/pack-fable-5.2-full.md
```

빌드하면 `pack-fable-5.2-full.manifest.json`에 어떤 파일의 어떤 해시가 들어갔는지 남는다. 재현성은 이 파일로만 주장한다.

## 4. 남은 구멍

공식 릴리스노트(31 KB)만 가진 사람이 "5.2 구현했다"고 말하면 도구·메모리·아티팩트 계층이 통째로 빠진 것이다. 반대로 CL4R1T4S 전재본은 **Anthropic 공식 문서가 아니라 제3자 전재**이므로, 그 내용이 5.2의 실제 배포본과 같은지는 별도 검증 대상이다. 이 저장소는 둘을 구분해 보관하고, 하네스가 어느 쪽을 썼는지 매니페스트에 기록한다.

또 하나: `claude-code-fable-5.2.txt`는 128K 문맥에 통째로 못 들어간다. 코드 축을 구현하려면 섹션 단위 분할 주입기(프롬프트 라우터)가 먼저 필요하다.
