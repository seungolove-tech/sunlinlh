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
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sample.db")

# ── DB 접속 안전장치 ────────────────────────────────────────────
# 챗봇은 5초 안에 답해야 한다. DB 가 느리거나 방화벽에 막히면
# 그 전에 포기하고 안내 문구를 내보내야 한다.
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "3"))
DB_READ_TIMEOUT = int(os.getenv("DB_READ_TIMEOUT", "3"))

# 사내 DB 를 외부에서 조회하므로 구간 암호화를 권장한다.
# DB 서버가 TLS 를 지원하면 DB_SSL=1 로 켤 것.
DB_SSL = os.getenv("DB_SSL", "0") == "1"

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

# ── FAQ 자동응답 (네이버 클라우드 CLOVA Studio) ─────────────────
# 콘솔에서 이용 신청·승인 후, 발급된 값을 아래 환경변수로 넣는다.
#
#   CLOVA_API_URL   호출 주소. 모델명이 끝에 붙는다. 콘솔에서 확인 후 맞출 것.
#   CLOVA_API_KEY   API 키 (nv- 로 시작). 코드에 적지 말고 환경변수로만 넣는다.
#   CLOVA_APIGW_KEY 구형 방식일 때만 사용. 신형(Bearer)은 비워둔다.
CLOVA_API_URL = os.getenv(
    "CLOVA_API_URL",
    "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-DASH-002",
)
CLOVA_API_KEY = os.getenv("CLOVA_API_KEY", "")
CLOVA_APIGW_KEY = os.getenv("CLOVA_APIGW_KEY", "")
CLOVA_REQUEST_ID = os.getenv("CLOVA_REQUEST_ID", "")

# 카카오 5초 제한 — 넘기지 않도록 짧게 잡는다
CLOVA_TIMEOUT = float(os.getenv("CLOVA_TIMEOUT", "3.5"))
CLOVA_MAX_TOKENS = int(os.getenv("CLOVA_MAX_TOKENS", "300"))

# FAQ 자료 파일 위치 (kakao-skill 폴더 기준 상대경로)
FAQ_PATH = os.getenv("FAQ_PATH", "faq.md")

# 질문 한 건당 프롬프트에 넣을 FAQ 항목 수 (많을수록 정확하지만 느리고 비쌈)
# head/body 가중치 적용으로 관련 없는 항목이 섞여도 순위가 밀리므로,
# 정답 항목이 빠질 확률을 낮추려고 8 → 10 으로 올린다.
FAQ_TOP_K = int(os.getenv("FAQ_TOP_K", "10"))
