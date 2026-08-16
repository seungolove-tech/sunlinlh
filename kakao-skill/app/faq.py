"""FAQ 자동 응답 — 네이버 클라우드 CLOVA Studio 호출 계층.

구조
    질문  →  FAQ 자료 + 지시문을 프롬프트로 조립  →  CLOVA Studio
          →  답변 문장  →  (main.py 가 카드로 포장)

설계 원칙
  · FAQ 자료에 있는 내용만으로 답한다. 없으면 상담원 연결로 안내한다.
  · 답변 길이를 제한한다. 카카오는 5초 안에 응답해야 한다.
  · 호출이 실패하거나 늦으면 예외를 올려 main.py 가 안내 문구로 대체한다.

CLOVA Studio 는 콘솔에서 이용 신청·승인을 받아야 호출할 수 있다.
엔드포인트 주소와 인증 헤더 형식은 콘솔에서 확인한 값을 환경변수로 넣는다.
"""
import asyncio
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, List, Optional

from .config import (
    CLOVA_API_KEY,
    CLOVA_API_URL,
    CLOVA_APIGW_KEY,
    CLOVA_MAX_TOKENS,
    CLOVA_REQUEST_ID,
    CLOVA_TIMEOUT,
    CONTACT_TEXT,
    FAQ_PATH,
    FAQ_TOP_K,
)

log = logging.getLogger("skill")

# FAQ 자료는 한 번만 읽어 메모리에 둔다 (배포 시 새로 읽힘)
_faq_cache: Optional[str] = None
_items_cache: Optional[List[str]] = None


def load_faq() -> str:
    """FAQ 자료 파일을 읽는다. 없으면 빈 문자열."""
    global _faq_cache
    if _faq_cache is None:
        path = Path(FAQ_PATH)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / FAQ_PATH
        try:
            _faq_cache = path.read_text(encoding="utf-8")
            log.info("FAQ 자료 로드 완료 (%d자)", len(_faq_cache))
        except OSError:
            log.warning("FAQ 자료 파일을 찾지 못함: %s", path)
            _faq_cache = ""
    return _faq_cache


def load_items() -> List[str]:
    """FAQ 문서를 '### ' 항목 단위로 쪼갠다.

    100건 전체(약 1만 8천 자)를 매 질문마다 보내면 비용도 크고
    응답도 느려 5초를 넘길 수 있다. 그래서 질문과 관련 있는 항목만
    골라 보낸다. 그 준비 작업이다.
    """
    global _items_cache
    if _items_cache is None:
        items, cur, cat = [], [], ""
        for line in load_faq().splitlines():
            if line.startswith("## ") and not line.startswith("### "):
                cat = line[3:].strip()
                continue
            if line.startswith("### "):
                if cur:
                    items.append("\n".join(cur).strip())
                cur = [f"[{cat}] " + line[4:].strip()]
                continue
            if cur and line.strip():
                cur.append(line.strip())
        if cur:
            items.append("\n".join(cur).strip())
        _items_cache = [i for i in items if i]
        log.info("FAQ 항목 %d건 분리 완료", len(_items_cache))
    return _items_cache


def _grams(text: str) -> set:
    """한글은 어미 변화가 많아 단어 단위 비교가 잘 안 맞는다.
    두 글자씩 잘라 비교하면 '재계약'/'재계약을'/'재계약이' 가 모두 겹친다."""
    t = "".join(ch for ch in text if ch.isalnum())
    return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def pick_related(question: str, k: int = FAQ_TOP_K) -> str:
    """질문과 겹치는 글자가 많은 순으로 FAQ 항목 k개를 골라 이어붙인다."""
    items = load_items()
    if not items:
        return load_faq()
    if len(items) <= k:
        return "\n\n".join(items)

    qg = _grams(question)
    scored = []
    for it in items:
        ig = _grams(it)
        overlap = len(qg & ig)
        # 긴 항목이 무조건 유리해지지 않도록 길이로 눌러준다
        scored.append((overlap / (len(ig) ** 0.5 + 1), it))
    scored.sort(key=lambda x: -x[0])
    return "\n\n".join(it for _, it in scored[:k])


SYSTEM_PROMPT = f"""너는 법무법인 선린 LH전세임대팀의 안내 담당자다.
입주자의 질문에 아래 [FAQ 자료]만을 근거로 답변한다.

지켜야 할 규칙
1. [FAQ 자료]에 있는 내용만으로 답한다. 자료에 없는 내용은 절대 추측하거나 지어내지 않는다.
2. 답할 근거가 자료에 없으면 다른 말을 덧붙이지 말고 정확히 "확인불가" 라고만 출력한다.
3. 개별 사안에 대한 법률 판단이나 유불리 예측은 하지 않는다.
4. 3문장 이내, 200자 이내로 답한다.
5. 인사말, 사족, 이모지를 쓰지 않고 질문에 대한 답만 쓴다.
6. 금액·기한·요건은 자료에 적힌 숫자를 그대로 쓴다. 반올림하거나 바꾸지 않는다.

[FAQ 자료]
{{faq}}
"""

# 자료에 근거가 없을 때 내보낼 고정 문구
NO_ANSWER = (
    "문의하신 내용은 담당자 확인이 필요합니다.\n"
    f"{CONTACT_TEXT} 로 문의해 주시면 안내해 드리겠습니다."
)


def _headers() -> dict:
    """콘솔에서 발급받은 형식에 맞춰 인증 헤더를 만든다.

    · 구형: X-NCP-CLOVASTUDIO-API-KEY + X-NCP-APIGW-API-KEY
    · 신형: Authorization: Bearer <키>
    CLOVA_APIGW_KEY 가 설정돼 있으면 구형으로, 없으면 신형으로 보낸다.
    """
    h = {"Content-Type": "application/json"}
    if CLOVA_APIGW_KEY:
        h["X-NCP-CLOVASTUDIO-API-KEY"] = CLOVA_API_KEY
        h["X-NCP-APIGW-API-KEY"] = CLOVA_APIGW_KEY
    else:
        h["Authorization"] = f"Bearer {CLOVA_API_KEY}"
    if CLOVA_REQUEST_ID:
        h["X-NCP-CLOVASTUDIO-REQUEST-ID"] = CLOVA_REQUEST_ID
    return h


def _extract(data: Any) -> Optional[str]:
    """응답 JSON에서 답변 문자열을 찾아낸다.

    CLOVA Studio 는 버전에 따라 응답 모양이 다르다.
    result.message.content / choices[0].message.content 등을 모두 훑는다.
    """
    if isinstance(data, dict):
        msg = data.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return msg["content"]
        if isinstance(data.get("content"), str) and data.get("role"):
            return data["content"]
        for v in data.values():
            found = _extract(v)
            if found:
                return found
    elif isinstance(data, list):
        for v in data:
            found = _extract(v)
            if found:
                return found
    return None


def _call_clova(question: str) -> str:
    """CLOVA Studio 를 호출해 답변 문자열을 돌려준다. 실패 시 예외."""
    if not CLOVA_API_URL or not CLOVA_API_KEY:
        raise RuntimeError("CLOVA_API_URL / CLOVA_API_KEY 미설정")

    body = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(faq=pick_related(question))},
            {"role": "user", "content": question},
        ],
        "topP": 0.8,
        "temperature": 0.1,   # 매번 같은 답이 나오도록 낮게 잡는다
        "repetitionPenalty": 1.1,
        "maxTokens": CLOVA_MAX_TOKENS,
    }

    req = urllib.request.Request(
        CLOVA_API_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=CLOVA_TIMEOUT) as res:
        raw = res.read().decode("utf-8", "replace")

    answer = _extract(json.loads(raw))
    if not answer:
        raise RuntimeError(f"응답에서 답변을 찾지 못함: {raw[:200]}")
    return answer.strip()


async def answer(question: str) -> str:
    """질문에 대한 답변을 돌려준다.

    근거가 없거나 호출에 실패하면 상담원 연결 안내 문구를 돌려준다.
    예외를 밖으로 던지지 않는다 — 챗봇은 어떤 경우에도 응답해야 한다.
    """
    if not load_faq():
        log.warning("FAQ 자료가 비어 있음")
        return NO_ANSWER

    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(_call_clova, question),
            timeout=CLOVA_TIMEOUT + 0.5,
        )
    except asyncio.TimeoutError:
        log.warning("CLOVA 응답 지연")
        return NO_ANSWER
    except urllib.error.HTTPError as e:
        # 어느 주소로 불렀는지 함께 남긴다. 환경변수가 반영됐는지 여기서 확인된다.
        log.error("CLOVA HTTP 오류 %s | 호출주소=%s | 키앞자리=%s | 본문=%s",
                  e.code, CLOVA_API_URL, (CLOVA_API_KEY or "")[:6] + "...",
                  e.read()[:200])
        return NO_ANSWER
    except Exception:
        log.exception("CLOVA 호출 실패")
        return NO_ANSWER

    # 모델이 "확인불가" 로 답하거나 빈 답을 주면 안내 문구로 바꾼다
    if not text or "확인불가" in text:
        return NO_ANSWER

    return text[:400]
