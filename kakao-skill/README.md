# sunlinlh — 카카오톡 챗봇 스킬 서버

법무법인 선린 LH 전세임대 챗봇용 스킬 서버.
이름 + 생년월일을 받아 계약 진행상태를 조회해 카카오 응답 카드로 돌려준다.

## 빠른 실행

```bash
pip install -r requirements.txt
python seed_sample.py                     # 테스트용 샘플 DB
export SKILL_TOKEN='긴-랜덤-문자열'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 구성

| 경로 | 설명 |
|---|---|
| `app/main.py` | 엔드포인트 `POST /skill/contract-status`, 응답 카드 |
| `app/kakao.py` | 요청 파싱 · 생년월일 정규화 · 응답 JSON 헬퍼 |
| `app/db.py` | **실제 DB 연결 시 여기만 수정** |
| `app/config.py` | 환경변수 |
| `schema_mysql.sql` | MySQL 테이블 예시 + 읽기전용 계정 |

자세한 구축 순서는 [README_카카오챗봇_스킬_구축가이드.md](README_카카오챗봇_스킬_구축가이드.md) 참고.

## 주의

- 카카오 스킬 서버는 **HTTPS 공인 도메인**, **응답 5초 이내** 필수
- `SKILL_TOKEN` 은 오픈빌더 스킬 헤더값(`Authorization: Bearer ...`)과 일치시킬 것
- `.env`, `*.db` 는 커밋하지 말 것 (.gitignore 처리됨)
