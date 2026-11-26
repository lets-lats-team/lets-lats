# Let's LATS

설비도면(DWG/DXF)에서 실외기 계통의 장비, 배관 연결, 길이를 읽어 LATS에 넣을 계통 초안을 만든다. 담당자는 원본 위치를 보며 값을 확인하고, 확인한 계통은 LATS에서 가져올 수 있는 SHD 파일과 검토표(CSV)로 내보낸다.

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

## 로컬 개발 환경

PostgreSQL 17.12와 S3 호환 저장소(MinIO)를 Docker Compose로 띄운다. `up --wait`와 Compose 파일의 최상위 `name`을 지원하는 Docker Compose(v2.3.3 이상)가 필요하고, 전체 기동은 v5.6.0에서 확인했다.

1. `.env.example`을 복사해 `.env`를 만들고 "로컬 Compose" 항목의 값을 채운다. 값이 비어 있으면 Compose가 기동을 멈춘다.
2. 저장소 루트에서 실행한다. Compose 파일이 `deploy/`에 있어 `--env-file .env`를 꼭 붙인다. 터미널에 같은 이름의 환경 변수가 있으면 `.env`보다 그 값이 먼저 쓰인다.

```bash
docker compose --env-file .env -f deploy/docker-compose.yml up -d --wait   # 기동, 상태 확인까지 기다림
docker compose --env-file .env -f deploy/docker-compose.yml ps             # 상태 보기
docker compose --env-file .env -f deploy/docker-compose.yml down           # 끄기 (데이터 유지)
```

로컬 DB와 파일을 모두 지우고 처음부터 시작할 때만 아래 명령을 쓴다.

```bash
docker compose --env-file .env -f deploy/docker-compose.yml down -v
```

| 서비스 | 주소 | 비고 |
|---|---|---|
| PostgreSQL | `127.0.0.1:5432` | `.env`의 `POSTGRES_*` 계정 |
| MinIO API | `http://127.0.0.1:9000` | 기동할 때 `S3_BUCKET` 버킷을 만든다 |
| MinIO 콘솔 | `http://127.0.0.1:9001` | 객체 조회용. `MINIO_ROOT_*` 계정 |

포트는 이 PC에서만 열린다. 시연 환경은 AWS(S3, RDS)이고 로컬 Compose는 개발과 장애 대비용이다.

## API 실행

```bash
cd api
./gradlew test        # Windows: .\gradlew.bat test
./gradlew bootRun
```

`.env`는 저장소에 올리지 않는다.
