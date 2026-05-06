# Daily Server Wakeup (Template)

**cron-job.org가 매일 정해진 시간에 GitHub `workflow_dispatch`를 호출**하는 방식으로 다음 3가지를 자동화하는 템플릿:

1. 지정한 URL을 GET해서 **슬립 상태 서버 깨우기** (Render / Fly.io / Heroku 같은 free tier)
2. Supabase 테이블에 오늘 날짜 한 줄 INSERT → **Supabase free tier 자동 일시정지 방지**
3. Notion DB에 실행 결과 자동 기록

**100% 무료** (cron-job.org Free 무제한 + GitHub Actions Free 월 2,000분 한도 / 이 워크플로우는 월 ~15분 사용).
**노트북/데스크탑이 꺼져있어도 작동.**

---

## ⚙️ 동작 흐름

```
┌─ cron-job.org (외부 cron, 99.9% 정시 트리거)
│   └─ 매일 정해진 시간 (예: KST 09:07)
│
├─ HTTP POST + GitHub PAT
│
├─ GitHub workflow_dispatch API
│   └─ daily.yml 트리거
│
├─ GitHub Actions Ubuntu runner
│   ├─ [1] GET <WAKE_URL>           → 슬립 서버 깨우기
│   ├─ [2] Supabase INSERT          → free tier 일시정지 방지
│   └─ [3] Notion DB row 추가        → 실행 로그
└─
```

> 💡 **왜 cron-job.org인가?** GitHub Actions schedule cron은 private repo + 활동 적은 repo에서 **30~50% skip되는 알려진 신뢰성 문제**가 있어. 외부 cron이 트리거하는 방식으로 우회. (자세한 건 아래 [트러블슈팅 노트](#-트러블슈팅-노트--미리-알아두면-좋은-함정))
>
> daily.yml에는 backup용 `schedule` cron도 들어있지만 신뢰하지 말 것. 메인은 cron-job.org.

## 📁 파일 구조

```
.
├── .github/workflows/daily.yml   # workflow_dispatch + (backup) schedule cron
├── wakeup.py                     # 실제 작업 스크립트
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🚀 셋업 가이드 (총 8단계, 약 30~40분)

### 1) 이 repo 사용

상단 **Use this template** 클릭 → 자기 GitHub 계정에 **private repo**로 만들기.

> ⚠️ **반드시 private**으로. 키 자체는 GitHub Secrets에 들어가서 안전하지만, README/코드의 부가 정보 노출을 막기 위함.

### 2) Supabase 정보 준비

Supabase Dashboard에서:
- **Project URL**: Settings → Data API → Project URL
- **Service Role Key**: Settings → API Keys → `service_role` (⚠️ `anon` 아님)
- **사용자 user_id**: Authentication → Users → 본인 → UID

### 3) Notion DB 만들기

자기 워크스페이스에 새 데이터베이스 생성. 컬럼 구성:

| 컬럼 이름 | 타입 | 옵션 |
|---|---|---|
| `Run` | Title | — |
| `RunAt` | Date | "Include time" 체크 |
| `Wake` | Select | Success (green) / Slow (yellow) / Failed (red) |
| `WakeTime` | Number | — |
| `WakeHTTP` | Number | — |
| `DB` | Select | Success (green) / Failed (red) |
| `DBMessageID` | Text | — |
| `Notes` | Text | — |

DB ID는 URL에서 추출: `https://www.notion.so/<DB_ID>` 의 32자리 hash. **Notion 내부 collection ID와 다른 값**이니 URL의 hash를 그대로 쓸 것. (자세한 건 [트러블슈팅 노트](#-트러블슈팅-노트--미리-알아두면-좋은-함정) 참고)

### 4) Notion Integration 만들기

1. https://www.notion.so/profile/integrations → **New integration**
2. Type: **Internal**
3. Workspace: 자기 워크스페이스 선택
4. **Save** → **Internal Integration Secret** 복사 (`secret_xxx...` 또는 `ntn_xxx...`)
5. 노션에서 위에서 만든 **DB 페이지 자체** 열기 → 우상단 `···` → **Connections** → 만든 integration 추가

> ⚠️ **부모 페이지에 추가하는 것만으로는 자식 DB에 권한 전파 안 될 수 있음**. DB 페이지에 직접 연결할 것.

### 5) GitHub Secrets 등록

repo Settings → Secrets and variables → Actions → New repository secret

**필수 (6개)**:

| Name | 설명 |
|---|---|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | `eyJhbG...`로 시작하는 service_role 키 |
| `SUPABASE_USER_ID` | UUID 형식 |
| `NOTION_TOKEN` | `secret_xxx...` 또는 `ntn_xxx...` integration token |
| `NOTION_DATABASE_ID` | DB URL의 32자리 hash |
| `WAKE_URL` | 깨울 서버의 endpoint URL |

**선택 (기본값과 다를 때만)**:

| Name | Default | 설명 |
|---|---|---|
| `SUPABASE_TABLE` | `chat_messages` | INSERT 대상 테이블 |
| `SUPABASE_PROFILE_TABLE` | `profiles` | 닉네임 조회 테이블 |
| `SUPABASE_PROFILE_NAME_COL` | `nickname` | profiles 테이블의 닉네임 컬럼 |
| `SUPABASE_SENDER_COL` | `sender_name` | INSERT 대상 sender 컬럼 |
| `SUPABASE_CONTENT_COL` | `content` | INSERT 대상 content 컬럼 |
| `SUPABASE_USER_COL` | `user_id` | INSERT 대상 user 컬럼 |
| `TZ_OFFSET_HOURS` | `9` | 시간대 오프셋 (KST=9) |
| `WAKE_TIMEOUT` | `150` | wake-up GET 타임아웃 (초) |

선택 secret을 사용하려면 `.github/workflows/daily.yml`의 주석 처리된 환경변수 라인을 풀어주세요.

### 6) workflow_dispatch 동작 확인

repo → **Actions** 탭 → **Daily Server Wakeup** → **Run workflow** → 결과 확인.

수동 실행으로 ✅ 성공 떠야 다음 단계 진행 가능. 실패하면 Secrets 6개를 다시 점검.

### 7) GitHub Personal Access Token 발급

cron-job.org가 GitHub Actions를 트리거하려면 토큰이 필요.

1. https://github.com/settings/tokens → **Fine-grained tokens** → **Generate new token**
2. 입력:
   - **Token name**: `cron-job-org-trigger`
   - **Expiration**: 1 year 또는 무제한 (또는 필요한 기간)
   - **Repository access**: **Only select repositories** → 이 repo 선택
   - **Permissions** → Repository permissions → **Add permissions** → `Actions` → **Read and write**
3. **Generate token** → `github_pat_xxxx...` 형식 토큰을 한 번만 표시함. **메모장에 보관.** (다시 못 봄)

### 8) cron-job.org 등록

1. https://cron-job.org 가입 (Free)
2. 우상단 계정 → **Settings** → **Timezone**을 자기 시간대(예: `Asia/Seoul`)로 설정
3. **Cronjobs** → **CREATE CRONJOB**
4. **Common 탭**:

| 항목 | 값 |
|---|---|
| Title | `Daily Server Wakeup` (자유) |
| URL | `https://api.github.com/repos/<USER>/<REPO>/actions/workflows/daily.yml/dispatches` |
| Schedule | "Every day at HH:MM" 선택 후 시각 입력 |

5. **Advanced 탭**:

| 항목 | 값 |
|---|---|
| Method | POST |
| Body type | application/json |
| Body | `{"ref": "main"}` |
| Header `Accept` | `application/vnd.github+json` |
| Header `Authorization` | `Bearer <Step 7의 PAT>` |
| Header `X-GitHub-Api-Version` | `2022-11-28` |

6. **CREATE / SAVE** → **ENABLED** 토글 ON

> ⚠️ **URL 끝에 다른 단어 안 붙도록 주의** (이 README 복사 시 인접 단어가 같이 묻을 수 있음). `dispatches`로 정확히 끝나야 함.

### 9) 첫 외부 트리거 테스트

cron-job.org Free 플랜은 "Run now" 버튼이 없음. 테스트하려면:

1. Schedule을 잠시 **현재 시각 + 5분** 으로 변경 → SAVE
2. 그 시각에 자동 트리거됨
3. cron-job.org → 해당 cronjob → **HISTORY**:
   - **Status 204** → ✅ 성공 (GitHub이 받았다는 뜻)
   - 401/403 → PAT 권한 문제 (Step 7 다시)
   - 404 → URL 오타
   - 422 → `ref` 또는 workflow 파일 이슈
4. 성공 확인되면 Schedule을 원하는 정기 시각으로 복원

이후 매일 정해진 시각에 자동 실행됨.

---

## ⏰ 스케줄 변경 (셋업 후)

### 메인 (cron-job.org)
cron-job.org → 해당 cronjob → EDIT → Schedule 변경 → SAVE.
**timezone이 자기 지역으로 설정되어 있는지 먼저 확인.**

### Backup (선택)
`.github/workflows/daily.yml`의 schedule cron도 같이 바꾸고 싶으면:

| 원하는 KST | UTC cron |
|---|---|
| 09:07 (default) | `7 0 * * *` |
| 08:30 | `30 23 * * *` (전날) |
| 평일만 09:07 | `7 0 * * 1-5` |

> backup이라 안 맞춰도 됨. 메인은 cron-job.org.

---

## 🎨 자기 사용 사례에 맞게 커스터마이징

### 메시지 형식 바꾸기
`wakeup.py`의 INSERT 부분에서 `today` 가공:
```python
"content": f"📅 {today} auto"
```

### 닉네임 자동 조회 끄기
`wakeup.py`의 nickname 조회 try 블록 → 고정값:
```python
sender_name = "automation-bot"
```

### 다중 wake URL
`WAKE_URL`을 콤마 구분으로 받아서 for 루프 돌리도록 수정.

---

## 🚧 트러블슈팅 노트 — 미리 알아두면 좋은 함정

이 템플릿은 4일간 직접 운영하면서 마주친 함정들을 정리한 결과물:

### 1. GitHub Actions schedule cron의 신뢰성 문제 (가장 큰 함정)
- 알려진 이슈: **private repo + 활동 적은 repo에서 30~50% cron skip**
- GitHub 공식 문서에도 "scheduled workflows may be delayed during periods of high loads. High load times include the start of every hour"라고 명시
- **해결**: 외부 cron(cron-job.org)이 `workflow_dispatch`를 호출하는 방식. 이 템플릿이 그렇게 구성된 이유.

### 2. 정시(00분) cron 더 잘 skip됨
- `0 0 * * *` (UTC 정시)는 트리거 요청이 몰려서 더 자주 skip됨
- **해결**: 7분처럼 비스듬한 오프셋. (이 템플릿 default가 `7 0 * * *`인 이유)

### 3. Notion DB ID 헷갈림
- Notion 내부 MCP가 쓰는 collection ID(`ec6db4f0-...`)와 표준 REST API가 쓰는 database ID(URL의 32자리 hash)가 **다른 값**
- **해결**: 항상 DB 페이지 URL 끝의 32자리 hash를 사용.

### 4. Notion Integration 권한 전파 안 됨
- 부모 페이지에 integration 연결해도 자식 DB에 자동 적용 안 되는 경우 있음
- **해결**: DB 페이지에 직접 connection 추가.

### 5. Node.js 20 deprecation (2026-06-02부터)
- 이미 daily.yml에 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` env 추가해뒀음
- 자동으로 Node 24 사용 → 호환성 미리 확인됨

---

## 🔒 보안 주의사항

### Supabase service_role
- **RLS 우회 마스터 키**. 절대 코드/공개 repo에 넣지 말 것.
- GitHub Secrets는 자동으로 암호화되며 Actions 로그에서도 마스킹됨.
- 그래도 repo는 **private** 권장 (실수 방지 + 부가 정보 보호).
- 키 노출 시: Supabase Dashboard → API → **Reset service_role key**.

### GitHub Personal Access Token
- Fine-grained, Actions Read/write, **이 repo만**으로 권한 최소화.
- 노출 시: GitHub → Settings → Tokens → **Revoke** 후 재발급 → cron-job.org 헤더 업데이트.

### cron-job.org
- 강력한 비밀번호 + (가능하면) 2FA 사용.

---

## 📜 License

MIT
