"""환경설정 — .env 또는 환경변수로 주입."""
import os

# ── DB 연결 문자열 ──────────────────────────────────────────────
# 개발(샘플): sqlite:///./sample.db
# 운영(MySQL): mysql+pymysql://USER:PASSWORD@HOST:3306/DBNAME?charset=utf8mb4
# 운영(MSSQL): mssql+pymssql://USER:PASSWORD@HOST:1433/DBNAME
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sample.db")

# ── 카카오 스킬 인증 ────────────────────────────────────────────
# 오픈빌더 스킬 등록 화면의 "헤더값 입력"에
#   Key: Authorization   Value: Bearer <이 값>
# 을 넣어두면, 외부에서 이 API를 함부로 호출하지 못한다.
SKILL_TOKEN = os.getenv("SKILL_TOKEN", "change-me-to-a-long-random-string")

# 개인정보 보호: 로그에 이름/생년월일 원문을 남기지 않는다
LOG_PII = os.getenv("LOG_PII", "0") == "1"

# 담당자 안내 문구
CONTACT_TEXT = os.getenv("CONTACT_TEXT", "법무법인 선린 LH팀 1670-0002")
