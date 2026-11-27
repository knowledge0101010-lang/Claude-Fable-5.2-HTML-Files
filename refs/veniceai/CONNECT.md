# veniceai 14개 — 연결 가능 여부 (실측)

조직은 **14개 / 610.8 MB**. 전부 받을 필요는 없고, 우리 스택에 바로 붙는 것은 셋이다.

| 저장소 | 크기 | 연결 방법 | 상태 |
|---|---:|---|---|
| `venice-cli` | 1.5 MB | `npx -y veniceai-cli …` | **실행 확인** — `--version` → `2.1.0` |
| `venice-mcp-server` | 20.3 MB | MCP stdio 서버 (`node dist/cli.js`) | 소스·도구 정의 확인, **도구 45개**(`venice_chat`, `venice_responses`, `venice_embeddings`, 이미지·비디오·오디오·음악·캐릭터) |
| `skills` | 0.5 MB | `skills/skills/*` 폴더를 DSH 스킬 디렉터리에 복사 | 스킬 폴더 확인 (`venice-auth`, `venice-api-keys`, `venice-audio-*` 등) |
| `api-docs` | 94.2 MB | 오프라인 문서 색인 | 색인만 |
| `x402-client` | 0.1 MB | 패키지 | 건당 과금 결제 경로 |
| `ironclaw` | 8.4 MB | Rust 재구현 | 참고용 |
| `base-org-web`, `pdf.js`, `builtinvenice`, `slackbot`, `venice-hermes-plugin`, `venice-android`, `egress-token-proxy` | — | — | 이번 범위 밖 |

## 막는 것 하나: API 키

`VENICE_API_KEY`가 이 기기에 없다(`env`, 셸 설정, `~/.venice` 모두 확인). 키 없이도
CLI 메타데이터와 MCP 도구 정의는 읽히지만, 실제 호출은 401이다.

## 붙이는 순서 (키를 넣는 순간부터)

1. 키 저장
   ```bash
   echo 'export VENICE_API_KEY=...' >> ~/.zshrc
   ```
2. CLI
   ```bash
   npx -y veniceai-cli chat 'hello'
   npx -y veniceai-cli image generate 'a stone nave at dawn'
   ```
3. MCP (DSH 프로필에 등록)
   ```yaml
   # refs/veniceai/dsh-mcp-patch.yml
   - id: mcp-venice
     config:
       command: npx
       args: ["-y", "@veniceai/mcp-server"]
       env:
         VENICE_API_KEY: "${VENICE_API_KEY}"
   ```
4. 스킬
   ```bash
   cp -R refs/veniceai/skills/skills/* "$DSH_HOME/skills/"
   ```

## 판정

**연결 가능하다.** 다만 세 가지 전제가 있다: 키, `npm install`(MCP 서버는 dist 미포함이라 빌드 필요),
그리고 디스크 여유(이 작업 시점 0.8 GB). 14개 전부가 아니라 위 3개만 붙이는 것이 맞다.
