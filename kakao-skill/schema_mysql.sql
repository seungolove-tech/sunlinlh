-- 운영 DB에 이미 계약 테이블이 있으면 이 파일은 참고용입니다.
-- app/db.py 의 LOOKUP_SQL 을 기존 테이블/컬럼명에 맞게 고치면 됩니다.

CREATE TABLE IF NOT EXISTS contracts (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    applicant_name VARCHAR(50)  NOT NULL COMMENT '입주자 성명',
    birth_ymd      CHAR(8)      NOT NULL COMMENT '생년월일 YYYYMMDD',
    status_code    VARCHAR(20)  NOT NULL COMMENT 'RECEIVED/REVIEWING/SUPPLEMENT/APPROVED/CONTRACTED/MOVED_IN',
    status_name    VARCHAR(50)  NOT NULL COMMENT '화면에 보여줄 상태명',
    house_address  VARCHAR(200) NULL,
    manager_name   VARCHAR(50)  NULL,
    memo           VARCHAR(300) NULL COMMENT '입주자에게 보여줄 안내문 (내부메모 금지)',
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_lookup (applicant_name, birth_ymd)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 챗봇 전용 읽기 계정 (권장)
-- CREATE USER 'chatbot_ro'@'%' IDENTIFIED BY '강한비밀번호';
-- GRANT SELECT ON slfastrack.contracts TO 'chatbot_ro'@'%';
