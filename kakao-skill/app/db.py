"""DB 조회 계층.

여기만 고치면 SQLite → MySQL → MSSQL 어디든 붙는다.
config.DATABASE_URL 만 바꾸면 되고, 실제 테이블/컬럼명이 다르면
아래 LOOKUP_SQL 의 SELECT 문만 우리 DB에 맞게 수정하면 된다.
"""
from typing import Optional, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import DATABASE_URL

_engine: Optional[Engine] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        kwargs: Dict[str, Any] = {"pool_pre_ping": True, "future": True}
        if not DATABASE_URL.startswith("sqlite"):
            # 커넥션이 죽어 5초 타임아웃을 넘기지 않도록 넉넉하지 않게 잡는다
            kwargs.update(pool_size=5, max_overflow=5, pool_recycle=1800)
        _engine = create_engine(DATABASE_URL, **kwargs)
    return _engine


# ────────────────────────────────────────────────────────────
# 실제 운영 DB에 붙일 때 이 SQL 하나만 바꾸면 된다.
# 반드시 바인드 파라미터(:name, :birth)를 쓸 것 — 문자열 붙이면 SQL 인젝션.
# ─────────────────────────────────────────────────────────────
LOOKUP_SQL = text(
    """
    SELECT  applicant_name   AS name,
            birth_ymd        AS birth,
            status_code      AS status_code,
            status_name      AS status_name,
            house_address    AS address,
            manager_name     AS manager,
            updated_at       AS updated_at,
            memo             AS memo
    FROM    contracts
    WHERE   REPLACE(applicant_name, ' ', '') = :name
      AND   SUBSTR(birth_ymd, -6) = :birth
    ORDER BY updated_at DESC
    LIMIT 5
    """
)
# SUBSTR(birth_ymd, -6) = 뒤에서 6자리.
# DB에 생년월일이 8자리(19900101)로 들어 있든 6자리(900101)로 들어 있든
# 둘 다 매칭되므로, 실제 컬럼 형식을 몰라도 그대로 쓸 수 있다.


def find_contracts(name: str, birth6: str) -> list[dict]:
    """이름 + 생년월일 6자리(YYMMDD)로 계약 건을 조회한다."""
    with get_engine().connect() as conn:
        rows = conn.execute(
            LOOKUP_SQL, {"name": name.replace(" ", ""), "birth": birth6}
        ).mappings().all()
    return [dict(r) for r in rows]
