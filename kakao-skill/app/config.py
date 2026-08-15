"""환경설정 — 같은 폴더의 .env 파일 또는 환경변수에서 읽는다."""
import os
from pathlib import Path

# 프로젝트 루트의 .env 파일을 자동으로 읽어들인다 (없으면 그냥 넘어감)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

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

# ── 테스트(데모) 모드 ───────────────────────────────────────────
# 1 이면 DB를 조회하지 않고, 어떤 이름·생년월일을 넣어도
# "접수중" 결과를 만들어서 돌려준다. 챗봇 연결만 먼저 확인할 때 사용.
# 실제 DB를 붙인 뒤에는 반드시 DEMO_MODE=0 으로 바꿀 것.
DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"
DEMO_STATUS_CODE = os.getenv("DEMO_STATUS_CODE", "RECEIVED")
DEMO_STATUS_NAME = os.getenv("DEMO_STATUS_NAME", "접수중")

# 개인정보 보호: 로그에 이름/생년월일 원문을 남기지 않는다
LOG_PII = os.getenv("LOG_PII", "0") == "1"

# 담당자 안내 문구
CONTACT_TEXT = os.getenv("CONTACT_TEXT", "법무법인 선린 LH팀 1670-0002")
