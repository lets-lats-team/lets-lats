# Let's LATS

설비도면(DWG/DXF)에서 실외기 계통의 장비, 배관 연결, 길이를 읽어 LATS에 넣을 계통 초안을 만든다. 담당자는 원본 위치를 보며 값을 확인하고, 확인한 계통은 SHD(X) 파일과 검토표(CSV)로 내보낸다.

## 구성

React 화면 → Nginx → Spring Boot API → PostgreSQL 작업 큐 → Python 워커. 원본과 산출물 파일은 Amazon S3에 둔다. API와 워커는 서로 호출하지 않고 PostgreSQL의 작업 행으로만 주고받는다.

## 폴더

| 폴더 | 내용 | 언어 |
|---|---|---|
| `api/` | 인증, 파일 등록, 분석·출력 요청, 검토 API. 스키마 마이그레이션(Flyway) | Java 25, Spring Boot |
| `worker/` | 작업 큐 처리, 도면 판독, 계통 계산, 문서 대조, 출력, AI 호출 | Python |
| `web/` | 작업 등록, 계통·도면 검토, 문서 대조, 산출물 화면 | React |
| `deploy/` | Docker Compose, Nginx 설정 | — |

워커의 AI 역할은 `worker/roles/<역할>/` 아래에 역할마다 따로 둔다.

## 실행

```bash
cd api
./gradlew test        # Windows: .\gradlew.bat test
./gradlew bootRun
```

환경 변수는 `.env.example`을 복사해 `.env`로 만들고 값을 채운다. `.env`는 저장소에 올리지 않는다.
