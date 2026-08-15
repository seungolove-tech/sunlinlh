"""샘플 SQLite DB 생성 — 실제 DB 붙이기 전 테스트용."""
import sqlite3, os

DB = os.getenv("SAMPLE_DB", "sample.db")
con = sqlite3.connect(DB)
con.executescript("""
DROP TABLE IF EXISTS contracts;
CREATE TABLE contracts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_name TEXT    NOT NULL,      -- 입주자 성명
    birth_ymd      TEXT    NOT NULL,      -- 생년월일 8자리 (19900101)
    status_code    TEXT    NOT NULL,      -- RECEIVED / REVIEWING / ...
    status_name    TEXT    NOT NULL,
    house_address  TEXT,
    manager_name   TEXT,
    memo           TEXT,
    updated_at     TEXT
);
CREATE INDEX idx_contracts_lookup ON contracts(applicant_name, birth_ymd);

INSERT INTO contracts
 (applicant_name, birth_ymd, status_code, status_name, house_address, manager_name, memo, updated_at)
VALUES
 ('홍길동','19900101','REVIEWING','권리분석 심사중','안양시 만안구 안양동 695-229','김상담','서류 이상 없이 심사 진행 중입니다.','2026-08-13 10:22:00'),
 ('김영희','19850320','SUPPLEMENT','서류 보완요청','수원시 팔달구 인계동 111-2','박상담','전입세대확인서가 누락되어 재제출이 필요합니다.','2026-08-14 15:40:00'),
 ('이철수','20000715','APPROVED','심사승인 (계약대기)','성남시 중원구 상대원동 22-5','최상담','계약일 조율을 위해 담당자가 연락드릴 예정입니다.','2026-08-15 09:05:00');
""")
con.commit(); con.close()
print("created", DB)
