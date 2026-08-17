"""챗봇 스킬 서버 — 계약 진행상태 조회.

실행:  uvicorn app.main:app --host 0.0.0.0 --port 8000

엔드포인트
  POST /skill/contract-status   카카오 i 오픈빌더 스킬용 (응답: 카카오 template 2.0)
  POST /agent/contract-status   sidetalk AI 에이전트용   (응답: sidetalk.card.v1)

두 엔드포인트는 조회 로직을 공유하고 응답 포맷만 다르다.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import faq, kakao
from .config import (
    CONTACT_TEXT,
    DEMO_MODE,
    DEMO_STATUS_CODE,
    DEMO_STATUS_NAME,
    LOG_PII,
    SKILL_TOKEN,
)
from .db import find_contracts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("skill")

app = FastAPI(title="선린 계약상태 조회 스킬", docs_url=None, redoc_url=None)

# 진행 단계 — 실제 DB의 status_code 에 맞춰 수정하세요
STAGES = [
    ("RECEIVED", "접수중"),
    ("REVIEWING", "권리분석 심사중"),
    ("SUPPLEMENT", "서류 보완요청"),
    ("APPROVED", "심사승인 (계약대기)"),
    ("CONTRACTED", "계약체결 완료"),
]
STAGE_INDEX = {code: i for i, (code, _) in enumerate(STAGES)}

# 안내 문구 (두 엔드포인트가 공유)
MSG_BAD_INPUT = (
    "이름과 생년월일을 다시 확인해 주세요.\n"
    "예) 홍길동 / 900101\n\n"
    "생년월일은 6자리 숫자로 입력해 주시면 됩니다."
)
MSG_DB_ERROR = (
    "지금은 조회가 어렵습니다. 잠시 후 다시 시도해 주세요.\n"
    f"급하신 경우 {CONTACT_TEXT} 로 문의 주시기 바랍니다."
)


def progress_bar(status_code: str) -> str:
    """접수중 ● ─ 심사중 ● ─ 승인 ○ ─ ... 형태의 진행표시."""
    idx = STAGE_INDEX.get(status_code)
    if idx is None:
        return ""
    marks = []
    for i, (_, label) in enumerate(STAGES):
        marks.append(("●" if i <= idx else "○") + " " + label)
    return "\n".join(marks)


# ════════════════════════════════════════════════════════════
# 공통 로직 — 조회와 문구 조립. 두 엔드포인트가 같이 쓴다.
# ════════════════════════════════════════════════════════════

def _lookup(name: str, birth: str) -> List[Dict[str, Any]]:
    """DEMO_MODE 면 가짜 응답, 아니면 실제 DB 조회. 예외는 그대로 올린다."""
    if DEMO_MODE:
        log.info("DEMO_MODE 응답")
        return [{
            "name": name,
            "birth": birth,
            "status_code": DEMO_STATUS_CODE,
            "status_name": DEMO_STATUS_NAME,
            "address": None,
            "manager": None,
            "updated_at": None,
            "memo": "※ 테스트용 임시 응답입니다. 실제 접수 내역이 아닙니다.",
        }]
    # 실제 DB 조회 (5초 제한 — 인덱스 필수: applicant_name, birth_ymd)
    return find_contracts(name, birth)


def _describe(rows: List[Dict[str, Any]]) -> str:
    """조회 결과 한 건을 사람이 읽을 본문으로 조립한다."""
    row = rows[0]
    updated = str(row.get("updated_at") or "")[:10]

    lines = [f"■ 진행상태 : {row.get('status_name') or '확인중'}"]
    if row.get("address"):
        lines.append(f"■ 대상주택 : {row['address']}")
    if updated:
        lines.append(f"■ 최종변경 : {updated}")
    if row.get("manager"):
        lines.append(f"■ 담당자   : {row['manager']}")
    if row.get("memo"):
        lines.append(f"\n{row['memo']}")

    bar = progress_bar(row.get("status_code") or "")
    if bar:
        lines.append("\n" + bar)

    if len(rows) > 1:
        lines.append(f"\n※ 접수 건이 {len(rows)}건 있어 가장 최근 건을 보여드립니다.")

    return "\n".join(lines)


def _not_found_text(name: str, birth: str) -> str:
    return (
        f"입력하신 정보({name} / {kakao.format_birth(birth)})로\n"
        "조회되는 접수 건이 없습니다.\n\n"
        "· 아직 접수 전이거나\n"
        "· 이름·생년월일이 접수 서류와 다르게 입력된 경우일 수 있습니다.\n\n"
        f"확인이 필요하시면 {CONTACT_TEXT} 로 문의해 주세요."
    )


def _authorized(request: Request) -> bool:
    """헤더의 Bearer 토큰 확인. 두 엔드포인트 공통."""
    if not SKILL_TOKEN:
        return True
    return request.headers.get("authorization", "") == f"Bearer {SKILL_TOKEN}"


@app.get("/health")
def health():
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# 1) 카카오 i 오픈빌더 스킬
# ════════════════════════════════════════════════════════════

@app.post("/skill/contract-status")
async def contract_status(request: Request):
    started = time.time()

    # 1) 인증 — 오픈빌더 "헤더값 입력"에 넣어둔 토큰 확인
    if not _authorized(request):
        log.warning("unauthorized skill call")
        return JSONResponse(status_code=401, content={"message": "unauthorized"})

    body = await request.json()

    # 2) 파라미터 추출 — 블록에서 지정한 파라미터 이름과 맞춰주세요
    raw_name = kakao.get_param(body, "name", "이름", "성함")
    raw_birth = kakao.get_param(body, "birth", "생년월일", "birthday")

    name = kakao.normalize_name(raw_name or "")
    birth = kakao.normalize_birth(raw_birth or "")

    if not name or not birth:
        return kakao.simple_text(
            MSG_BAD_INPUT,
            quick_replies=[kakao.qr_message("다시 조회하기", "권리분석 진행상태 조회")],
        )

    # 3) 조회
    try:
        rows = _lookup(name, birth)
    except Exception:
        log.exception("db error")
        return kakao.simple_text(MSG_DB_ERROR)

    if LOG_PII:
        log.info("lookup name=%s birth=%s hit=%d", name, birth, len(rows))
    else:
        log.info("lookup hit=%d elapsed=%.2fs", len(rows), time.time() - started)

    # 4) 응답 만들기
    if not rows:
        return kakao.simple_text(
            _not_found_text(name, birth),
            quick_replies=[kakao.qr_message("다시 조회하기", "권리분석 진행상태 조회")],
        )

    return kakao.text_card(
        title=f"{name}님 권리분석 진행상태",
        description=_describe(rows),
        quick_replies=[
            kakao.qr_message("다시 조회하기", "권리분석 진행상태 조회"),
            kakao.qr_message("상담원 연결", "상담원 연결"),
        ],
    )


# ════════════════════════════════════════════════════════════
# 2) sidetalk AI 에이전트 (응답 포맷: sidetalk.card.v1)
# ════════════════════════════════════════════════════════════

# 카드 아래 버튼. action 은 "message"(대신 입력) 또는 "url"(링크 열기)
AGENT_BUTTONS = [
    {"label": "다시 조회하기", "action": "message", "value": "권리분석 진행상태 조회"},
]


def agent_card(title: str, description: str,
               buttons: Optional[List[dict]] = None) -> Dict[str, Any]:
    """sidetalk.card.v1 형식 응답을 만든다.

    items 가 한 건뿐이라 displayMode 는 어떤 값이든 결과가 같지만,
    매뉴얼 예시를 그대로 따라 "random" 을 쓴다.
    """
    item: Dict[str, Any] = {
        "type": "text",
        "title": title[:50],
        "description": description,
    }
    if buttons:
        item["buttons"] = buttons
    return {
        "schema": "sidetalk.card.v1",
        "cardType": "text",
        "displayMode": "random",
        "items": [item],
    }


def agent_get_param(data: Any, *keys: str) -> Optional[str]:
    """에이전트가 보낸 본문에서 값을 찾는다.

    설정 화면에서 파라미터를 어떤 이름으로 매핑했는지에 따라
    최상위에 올 수도, params/data 같은 키 아래에 중첩될 수도 있어
    한 단계씩 내려가며 훑는다.
    """
    if not isinstance(data, dict):
        return None
    for key in keys:
        v = data.get(key)
        if isinstance(v, (str, int)) and str(v).strip():
            return str(v).strip()
    for v in data.values():
        if isinstance(v, dict):
            found = agent_get_param(v, *keys)
            if found:
                return found
    return None


NAME_KEYS = ("name", "이름", "성함", "applicant_name")
BIRTH_KEYS = (
    # sidetalk 이 실제로 보내는 키 (2026-08 확인)
    "birthdate", "birthDate", "birth_date",
    "birth", "생년월일", "birthday", "birth_ymd", "dob",
    # 트리거에 "주민번호앞자리6자리" 로 등록한 경우
    "주민번호앞자리6자리", "주민번호앞자리", "주민번호",
    "주민등록번호앞자리6자리", "rrn6", "ssn6",
)


@app.get("/agent/contract-status")
async def agent_contract_status_get(request: Request):
    """GET 우회로 — sidetalk 의 POST 본문 전송이 고쳐질 때까지만 쓴다.

    GET 은 이름·생년월일이 URL 에 실려 접속기록에 개인정보가 남는다.
    그래서 DEMO_MODE 일 때만 열어둔다. 실제 DB 를 붙이는 순간
    (DEMO_MODE=0) 이 경로는 자동으로 막히므로, 실 개인정보가
    URL 로 흐르는 일은 구조적으로 생기지 않는다.
    """
    if not _authorized(request):
        log.warning("unauthorized agent call (GET)")
        return JSONResponse(status_code=401, content={"message": "unauthorized"})

    if not DEMO_MODE:
        log.warning("GET 차단 — DEMO_MODE 가 꺼져 있음")
        return agent_card(
            "이 방식은 사용할 수 없습니다",
            "개인정보 보호를 위해 GET 방식 조회는 테스트 모드에서만 열려 있습니다.\n"
            "POST 방식으로 요청해 주세요.",
        )

    return _agent_respond(dict(request.query_params), "GET")


@app.post("/agent/contract-status")
async def agent_contract_status(request: Request):
    """sidetalk 'API 요청' 액션이 호출하는 엔드포인트.

    가능하면 POST 를 쓸 것. GET 은 이름·생년월일이 URL 에 남는다.
    헤더에 Authorization / Bearer <SKILL_TOKEN> 을 등록해야 통과한다.
    """
    if not _authorized(request):
        log.warning("unauthorized agent call")
        return JSONResponse(status_code=401, content={"message": "unauthorized"})

    try:
        body = await request.json()
    except Exception:
        body = {}

    return _agent_respond(body, "POST")


def _agent_respond(body: Any, method: str) -> Dict[str, Any]:
    """파라미터 추출 → 조회 → 카드 생성. GET·POST 가 함께 쓴다."""
    started = time.time()

    raw_name = agent_get_param(body, *NAME_KEYS)
    raw_birth = agent_get_param(body, *BIRTH_KEYS)

    name = kakao.normalize_name(raw_name or "")
    birth = kakao.normalize_birth(raw_birth or "")

    if not name or not birth:
        return agent_card("조회 정보 확인 필요", MSG_BAD_INPUT, AGENT_BUTTONS)

    try:
        rows = _lookup(name, birth)
    except Exception:
        log.exception("db error")
        return agent_card("일시적인 오류", MSG_DB_ERROR, AGENT_BUTTONS)

    if LOG_PII:
        log.info("agent lookup name=%s birth=%s hit=%d", name, birth, len(rows))
    else:
        log.info("agent lookup hit=%d elapsed=%.2fs", len(rows), time.time() - started)

    if not rows:
        return agent_card("조회 결과 없음", _not_found_text(name, birth), AGENT_BUTTONS)

    return agent_card(
        f"{name}님 권리분석 진행상태",
        _describe(rows),
        AGENT_BUTTONS,
    )


# ════════════════════════════════════════════════════════════
# 3) FAQ 자동 응답 — 오픈빌더 폴백 블록에 연결한다.
#    사이드톡 같은 외부 업체를 거치지 않고, 우리 서버가 직접
#    FAQ 자료를 근거로 답변을 만든다.
# ════════════════════════════════════════════════════════════

def _utterance(body: Any) -> str:
    """사용자가 실제로 입력한 문장을 꺼낸다."""
    if not isinstance(body, dict):
        return ""
    ur = body.get("userRequest") or {}
    text = ur.get("utterance")
    if isinstance(text, str) and text.strip():
        return text.strip()
    # 폴백 블록이 아닌 경로로 들어온 경우까지 대비
    return (kakao.get_param(body, "question", "질문", "query") or "").strip()


@app.post("/skill/faq")
async def skill_faq(request: Request):
    """폴백 블록에서 호출한다. 어떤 경우에도 200 과 카카오 응답을 돌려준다."""
    started = time.time()

    if not _authorized(request):
        log.warning("unauthorized faq call")
        return JSONResponse(status_code=401, content={"message": "unauthorized"})

    try:
        body = await request.json()
    except Exception:
        body = {}

    question = _utterance(body)
    if len(question) < 2:
        return kakao.simple_text(
            "궁금하신 내용을 문장으로 입력해 주세요.\n"
            "예) 권리분석은 얼마나 걸리나요?"
        )

    text = await faq.answer(question)
    log.info("faq answered in %.2fs (질문 %d자)", time.time() - started, len(question))

return kakao.simple_text(text)
