"""카카오톡 챗봇 스킬 서버 — 계약 진행상태 조회.

실행:  uvicorn app.main:app --host 0.0.0.0 --port 8000
엔드포인트: POST /skill/contract-status   (오픈빌더 스킬 URL 에 등록)
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import kakao
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


def progress_bar(status_code: str) -> str:
    """접수완료 ● ─ 심사중 ● ─ 승인 ○ ─ ... 형태의 한 줄 진행표시."""
    idx = STAGE_INDEX.get(status_code)
    if idx is None:
        return ""
    marks = []
    for i, (_, label) in enumerate(STAGES):
        marks.append(("●" if i <= idx else "○") + " " + label)
    return "\n".join(marks)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/skill/contract-status")
async def contract_status(request: Request):
    started = time.time()

    # 1) 인증 — 오픈빌더 "헤더값 입력"에 넣어둔 토큰 확인
    auth = request.headers.get("authorization", "")
    if SKILL_TOKEN and auth != f"Bearer {SKILL_TOKEN}":
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
            "이름과 생년월일을 다시 확인해 주세요.\n"
            "예) 홍길동 / 900101\n\n"
            "생년월일은 6자리 숫자로 입력해 주시면 됩니다.",
            quick_replies=[kakao.qr_message("다시 조회하기", "권리분석 진행상태 조회")],
        )

    # 3) 조회
    if DEMO_MODE:
        # 테스트 모드: DB를 보지 않고, 입력한 이름 그대로 "접수중"을 만들어 돌려준다
        log.info("DEMO_MODE 응답")
        rows = [{
            "name": name,
            "birth": birth,
            "status_code": DEMO_STATUS_CODE,
            "status_name": DEMO_STATUS_NAME,
            "address": None,
            "manager": None,
            "updated_at": None,
            "memo": "※ 테스트용 임시 응답입니다. 실제 접수 내역이 아닙니다.",
        }]
    else:
        # 실제 DB 조회 (5초 제한 — 인덱스 필수: applicant_name, birth_ymd)
        try:
            rows = find_contracts(name, birth)
        except Exception:
            log.exception("db error")
            return kakao.simple_text(
                "지금은 조회가 어렵습니다. 잠시 후 다시 시도해 주세요.\n"
                f"급하신 경우 {CONTACT_TEXT} 로 문의 주시기 바랍니다."
            )

    if LOG_PII:
        log.info("lookup name=%s birth=%s hit=%d", name, birth, len(rows))
    else:
        log.info("lookup hit=%d elapsed=%.2fs", len(rows), time.time() - started)

    # 4) 응답 만들기
    if not rows:
        return kakao.simple_text(
            f"입력하신 정보({name} / {kakao.format_birth(birth)})로\n"
            "조회되는 접수 건이 없습니다.\n\n"
            "· 아직 접수 전이거나\n"
            "· 이름·생년월일이 접수 서류와 다르게 입력된 경우일 수 있습니다.\n\n"
            f"확인이 필요하시면 {CONTACT_TEXT} 로 문의해 주세요.",
            quick_replies=[kakao.qr_message("다시 조회하기", "권리분석 진행상태 조회")],
        )

    row = rows[0]
    status_name = row.get("status_name") or "확인중"
    updated = str(row.get("updated_at") or "")[:10]

    lines = [f"■ 진행상태 : {status_name}"]
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

    return kakao.text_card(
        title=f"{name}님 권리분석 진행상태",
        description="\n".join(lines),
        quick_replies=[
            kakao.qr_message("다시 조회하기", "권리분석 진행상태 조회"),
            kakao.qr_message("상담원 연결", "상담원 연결"),
        ],
    )
