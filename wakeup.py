#!/usr/bin/env python3
"""
Daily Server Wakeup Template

매일 정해진 시간에:
1. 지정한 URL을 GET해서 슬립 상태 서버를 깨움 (Render/Heroku 같은 free tier 대응)
2. Supabase 테이블에 오늘 날짜를 INSERT (Supabase free tier 일시정지 방지)
3. Notion DB에 실행 결과 로그

GitHub Actions cron으로 매일 실행. 자세한 내용은 README.md 참고.
"""
import os
import sys
import time
import requests
from datetime import datetime, timezone, timedelta

# ── 환경변수 (GitHub Secrets에서 주입) ──────────────────
SUPABASE_URL          = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY           = os.environ["SUPABASE_SERVICE_KEY"]
USER_ID               = os.environ["SUPABASE_USER_ID"]
NOTION_TOKEN          = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID    = os.environ["NOTION_DATABASE_ID"]
WAKE_URL              = os.environ["WAKE_URL"]
WAKE_TIMEOUT          = int(os.environ.get("WAKE_TIMEOUT", "150"))

# Supabase 테이블/컬럼 설정 (자기 프로젝트에 맞게 환경변수로 주입)
SB_TABLE              = os.environ.get("SUPABASE_TABLE", "chat_messages")
SB_PROFILE_TABLE      = os.environ.get("SUPABASE_PROFILE_TABLE", "profiles")
SB_PROFILE_NAME_COL   = os.environ.get("SUPABASE_PROFILE_NAME_COL", "nickname")
SB_SENDER_COL         = os.environ.get("SUPABASE_SENDER_COL", "sender_name")
SB_CONTENT_COL        = os.environ.get("SUPABASE_CONTENT_COL", "content")
SB_USER_COL           = os.environ.get("SUPABASE_USER_COL", "user_id")

# 시간대 설정 (default: KST)
TZ_OFFSET             = int(os.environ.get("TZ_OFFSET_HOURS", "9"))

# ── 시간 ─────────────────────────────────────────────────
TZ = timezone(timedelta(hours=TZ_OFFSET))
now = datetime.now(TZ)
today = now.strftime("%Y-%m-%d")
now_iso = now.strftime(f"%Y-%m-%dT%H:%M:%S{'+' if TZ_OFFSET >= 0 else ''}{TZ_OFFSET:02d}:00")
run_label = f"{today} {now.strftime('%H:%M')}"

# ── [1] 외부 서버 깨우기 ─────────────────────────────────
print(f"[1/3] Wake-up GET {WAKE_URL}")
wake_error = ""
start = time.time()
try:
    r = requests.get(WAKE_URL, timeout=WAKE_TIMEOUT)
    wake_time = time.time() - start
    wake_http = r.status_code
    wake_ok = wake_http == 200
except requests.RequestException as e:
    wake_time = time.time() - start
    wake_http = 0
    wake_ok = False
    wake_error = f"{type(e).__name__}: {e}"

if not wake_ok:
    wake_status = "Failed"
elif wake_time < 10:
    wake_status = "Success"
else:
    wake_status = "Slow"
print(f"  → {wake_status} (HTTP {wake_http}, {wake_time:.2f}s) {wake_error}")

# ── [2] Supabase INSERT ──────────────────────────────────
print(f"[2/3] Supabase {SB_PROFILE_TABLE} 조회 + {SB_TABLE} INSERT")
sb_headers = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}
sb_status = "Failed"
sb_message_id = ""
sb_error = ""
sender_name = ""

try:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{SB_PROFILE_TABLE}",
        params={"id": f"eq.{USER_ID}", "select": SB_PROFILE_NAME_COL},
        headers=sb_headers,
        timeout=15,
    )
    r.raise_for_status()
    sender_name = r.json()[0][SB_PROFILE_NAME_COL]

    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{SB_TABLE}",
        headers={**sb_headers, "Prefer": "return=representation"},
        json={
            SB_USER_COL: USER_ID,
            SB_SENDER_COL: sender_name,
            SB_CONTENT_COL: today,
        },
        timeout=15,
    )
    r.raise_for_status()
    sb_message_id = r.json()[0].get("id", "")
    sb_status = "Success"
except Exception as e:
    sb_error = f"{type(e).__name__}: {e}"
print(f"  → {sb_status} ({sender_name or '?'}) id={sb_message_id} {sb_error}")

# ── [3] Notion 로그 ──────────────────────────────────────
print("[3/3] Notion DB row 추가")
notes_parts = ["GitHub Actions auto-run"]
if wake_ok:
    notes_parts.append(f"wake {wake_time:.1f}s ({'hot' if wake_time < 10 else 'cold start'})")
else:
    notes_parts.append(f"wake fail: {wake_error or 'HTTP ' + str(wake_http)}")
if sb_status == "Failed":
    notes_parts.append(f"DB fail: {sb_error}")
notes = " · ".join(notes_parts)

notion_payload = {
    "parent": {"database_id": NOTION_DATABASE_ID},
    "properties": {
        "Run":         {"title":     [{"text": {"content": run_label}}]},
        "RunAt":       {"date":      {"start": now_iso}},
        "Wake":        {"select":    {"name": wake_status}},
        "WakeTime":    {"number":    round(wake_time, 2)},
        "WakeHTTP":    {"number":    wake_http},
        "DB":          {"select":    {"name": sb_status}},
        "DBMessageID": {"rich_text": [{"text": {"content": sb_message_id}}]},
        "Notes":       {"rich_text": [{"text": {"content": notes[:1900]}}]},
    },
}

r = requests.post(
    "https://api.notion.com/v1/pages",
    headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    },
    json=notion_payload,
    timeout=30,
)
notion_ok = r.status_code in (200, 201)
print(f"  → Notion HTTP {r.status_code}")
if not notion_ok:
    print(f"  Body: {r.text[:500]}")

# ── Summary + Exit ───────────────────────────────────────
print("\n=== Summary ===")
print(f"Wake:   {wake_status} (HTTP {wake_http}, {wake_time:.2f}s)")
print(f"DB:     {sb_status} {sb_message_id}")
print(f"Notion: {'OK' if notion_ok else 'FAIL'}")

sys.exit(0 if (wake_ok and sb_status == "Success" and notion_ok) else 1)
