"""카카오 i 오픈빌더 스킬 요청/응답 헬퍼."""
from typing import Any, Dict, List, Optional
import json
import re

# ── 요청에서 파라미터 꺼내기 ────────────────────────────────────
# 오픈빌더는 action.params(문자열)와 action.detailParams(원문+정규화값)를 함께 보낸다.
# 엔티티(sys.date 등)를 쓰면 detailParams 쪽에 JSON 문자열이 들어오므로 둘 다 본다.


def get_param(body: Dict[str, Any], *keys: str) -> Optional[str]:
    """params/detailParams 에서 키를 순서대로 찾아 첫 값을 돌려준다."""
    action = body.get("action") or {}
    params = action.get("params") or {}
    detail = action.get("detailParams") or {}

    for key in keys:
        if key in detail:
            d = detail[key] or {}
            v = d.get("value") or d.get("origin")
            if v:
                # sys.date 등은 value가 '{"date":"2026-08-15"}' 형태의 JSON 문자열
                if isinstance(v, str) and v.strip().startswith("{"):
                    try:
                        obj = json.loads(v)
                        for k in ("date", "value", "text"):
                            if obj.get(k):
                                return str(obj[k])
                    except json.JSONDecodeError:
                        pass
                return str(v).strip()
        if params.get(key):
            return str(params[key]).strip()
    return None


# ── 생년월일 정규화 ────────────────────────────────────────────
_DIGITS = re.compile(r"\D+")


def normalize_birth(raw: str) -> Optional[str]:
    """'1990-01-01', '90.1.1', '900101', '1990년 1월 1일' → '19900101'."""
    if not raw:
        return None
    d = _DIGITS.sub("", raw)

    if len(d) == 8:
        pass
    elif len(d) == 6:
        # 2자리 연도 → 00~현재년도 두자리는 2000년대, 나머지는 1900년대
        yy, rest = int(d[:2]), d[2:]
        century = 2000 if yy <= 26 else 1900
        d = f"{century + yy}{rest}"
    else:
        return None

    y, m, day = int(d[:4]), int(d[4:6]), int(d[6:8])
    if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= day <= 31):
        return None
    return d


def normalize_name(raw: str) -> Optional[str]:
    if not raw:
        return None
    name = raw.strip().replace(" ", "")
    # 한글 2~5자 / 영문만 허용 (엉뚱한 발화가 이름으로 들어오는 것 방지)
    if re.fullmatch(r"[가-힣]{2,5}|[A-Za-z]{2,20}", name):
        return name
    return None


# ── 응답 만들기 ────────────────────────────────────────────────

def simple_text(text: str, quick_replies: Optional[List[dict]] = None) -> dict:
    tpl: Dict[str, Any] = {"outputs": [{"simpleText": {"text": text}}]}
    if quick_replies:
        tpl["quickReplies"] = quick_replies
    return {"version": "2.0", "template": tpl}


def text_card(title: str, description: str,
              buttons: Optional[List[dict]] = None,
              quick_replies: Optional[List[dict]] = None) -> dict:
    card: Dict[str, Any] = {"title": title[:50], "description": description[:400]}
    if buttons:
        card["buttons"] = buttons
    tpl: Dict[str, Any] = {"outputs": [{"textCard": card}]}
    if quick_replies:
        tpl["quickReplies"] = quick_replies
    return {"version": "2.0", "template": tpl}


def qr_message(label: str, message: str) -> dict:
    return {"label": label, "action": "message", "messageText": message}


def qr_block(label: str, block_id: str, message: Optional[str] = None) -> dict:
    qr = {"label": label, "action": "block", "blockId": block_id}
    if message:
        qr["messageText"] = message
    return qr
