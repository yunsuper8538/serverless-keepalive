# Daily Server Wakeup (Template)

GitHub Actions cron으로 매일 정해진 시간에:

1. 지정한 URL을 GET해서 **슬립 상태 서버 깨우기** (Render / Fly.io / Heroku 같은 free tier)
2. Supabase 테이블에 오늘 날짜 한 줄 INSERT → **Supabase free tier 자동 일시정지 방지**
3. Notion DB에 실행 결과 자동 기록

100% 무료 (GitHub Actions Free 한도 월 2,000분 / 이 워크플로우는 월 ~15분 사용).
**노트북/데스크탑이 꺼져있어도 GitHub 클라우드에서 자동 실행.**

---

## ⚙️ 동작 흐름

```
┌─ GitHub Actions cron (매일 정해진 시간)
│
├─ [1] GET <WAKE_URL>           → Render 백엔드 깨우기
├─ [2] Supabase INSERT          → free tier 일시정지 방지
└─ [3] Notion DB row 추가        → 실행 로그
```

## 📁 파일 구조

```
.
├── .github/workflows/daily.yml   # cron + 실행 정의
├── wakeup.py                     # 실제 작업 스크립트
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🚀 셋업 가이드

### 1) 이 repo fork (또는 사용)

상단 **Use this template** 또는 **Fork** 클릭 → 자기 GitHub 계정에 **private repo**로 만들기.

> ⚠️ **반드시 private**으로. 키 자체는 GitHub Secrets에 들어가서 안전하지만, README/코드의 부가 정보 노출을 막기 위함.

### 2) Supabase 정보 준비

Supabase Dashboard에서:
- Project URL: Settings → Data API → Project URL
- Service Role Key: Settings → API Keys → `service_role` (⚠️ `anon` 아님!)
- 사용자 user_id: Authentication → Users → 본인 → UID

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

DB ID는 URL에서 추출: `https://www.notion.so/<DB_ID>` 의 32자리 hash.

### 4) Notion Integration 만들기

1. https://www.notion.so/profile/integrations → **New integration**
2. Type: **Internal**
3. Workspace: 자기 워크스페이스 선택
4. **Save** → **Internal Integration Secret** 복사 (`secret_xxx...`)
5. 노션에서 위에서 만든 DB 페이지 열기 → 우상단 `···` → **Connections** → 만든 integration 추가

### 5) GitHub Secrets 등록

repo Settings → Secrets and variables → Actions → New repository secret

**필수 (6개):**

| Name | 설명 |
|---|---|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | `eyJhbG...`로 시작하는 service_role 키 |
| `SUPABASE_USER_ID` | UUID 형식 |
| `NOTION_TOKEN` | `secret_xxx...` integration token |
| `NOTION_DATABASE_ID` | DB URL의 32자리 hash |
| `WAKE_URL` | 깨울 서버의 endpoint URL |

**선택 (기본값과 다를 때만 등록):**

| Name | Default | 설명 |
|---|---|---|
| `SUPABASE_TABLE` | `chat_messages` | INSERT 대상 테이블 |
| `SUPABASE_PROFILE_TABLE` | `profiles` | nickname 조회 테이블 |
| `SUPABASE_PROFILE_NAME_COL` | `nickname` | profiles 테이블의 닉네임 컬럼 |
| `SUPABASE_SENDER_COL` | `sender_name` | INSERT 대상 sender 컬럼 |
| `SUPABASE_CONTENT_COL` | `content` | INSERT 대상 content 컬럼 |
| `SUPABASE_USER_COL` | `user_id` | INSERT 대상 user 컬럼 |
| `TZ_OFFSET_HOURS` | `9` | 시간대 오프셋 (KST=9) |
| `WAKE_TIMEOUT` | `150` | wake-up GET 타임아웃 (초) |

선택 secret을 사용하려면 `.github/workflows/daily.yml`에서 주석 처리된 환경변수 라인의 주석을 풀어줘.

### 6) 첫 실행 테스트

repo → **Actions** 탭 → **Daily Server Wakeup** → **Run workflow** → 결과 확인.

성공하면 매일 cron 시간에 자동 실행됨.

---

## ⏰ 스케줄 변경

`.github/workflows/daily.yml`의 `cron` 수정 (UTC 기준).

| 원하는 KST | UTC cron |
|---|---|
| 09:00 (default) | `0 0 * * *` |
| 08:30 | `30 23 * * *` (전날) |
| 평일만 09:00 | `0 0 * * 1-5` |
| 매 시간 정각 | `0 * * * *` |
| 15분마다 | `*/15 * * * *` |

> ⚠️ GitHub Actions cron은 부하 분산 때문에 0~15분 정도 지연될 수 있음.
> 정확한 시각이 중요하면 cron-job.org 같은 외부 서비스 추천.

---

## 🎨 자기 사용 사례에 맞게 커스터마이징

### 메시지 형식 바꾸기
`wakeup.py`의 INSERT 부분에서 `today`(예: `"2026-05-04"`)를 원하는 형태로 가공:
```python
"content": f"📅 {today} auto"
```

### 닉네임 자동 조회 끄기
`wakeup.py`의 nickname 조회 try 블록을 주석 처리하고 고정값 사용:
```python
sender_name = "automation-bot"
```

### 다중 wake URL
`WAKE_URL`을 콤마 구분으로 받아서 for 루프 돌리도록 수정.

---

## 🔒 보안 주의사항

- `SUPABASE_SERVICE_KEY`는 RLS를 우회하는 마스터 키. 절대 코드에 직접 넣지 마세요.
- GitHub Secrets는 자동으로 암호화되며 Actions 로그에서도 마스킹됩니다.
- 그래도 repo는 **private** 권장 (실수 방지 + 부가 정보 보호).
- 키 노출 시: Supabase Dashboard → API → Reset service_role key.

## 📜 License

MIT
