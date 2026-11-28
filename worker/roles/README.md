# AI 역할 L2·L3와 평가 도구 (김선진)

AI 설계 v0.8(11.4 역할 모듈 계약 1.1) 기준으로 만든 AI 역할 코드와, 실제 모델을 정답셋과 맞대 보는 평가 도구.

## 폴더

| 경로 | 내용 |
|---|---|
| `worker/roles/` (여기) | 역할 모듈 계약(`contract.py`), 계약 검사(`conformance.py`), 가짜 엔진(`testing.py`: 교차 확인·G5·보류 코드) |
| `worker/roles/l3_spec/` | **L3 시방서·공고문 조건 추출** — 읽기(HWP·PDF), 조항 나누기, 프롬프트 `l3-v1~v3`, G2·G3 검사. 결정·시험 결과는 [README](l3_spec/README.md) |
| `worker/steps/s5_docs/` | **L2 내역서 항목 연결** (11-25 수정본. 계약 구조 `worker/roles/`로 옮기기 전) |
| `eval/` | 평가 실행기 `run_l2_eval.py`·`run_l3_eval.py`·`run_vision_eval.py`, 채점(`l2_eval/`, `l3_eval/`), Vision 시험 키트(`vision_kit/`), 테스트 |

## 설치와 테스트

저장소 루트에서:

```bash
pip install -r eval/requirements.txt          # worker/requirements.txt 포함
python -X utf8 -m pytest -q -p no:cacheprovider worker/roles worker/tests eval/tests
```

원본 문서가 없어도 테스트는 돈다. 원본이 필요한 시험(S24~S26 조항 수 등)은 건너뛴다.

## 저장소에 없는 것

- **나라장터 원본(HWP·PDF·XLSX·DWG)과 정답 엑셀**: 공개 권한 미확인이라 넣지 않았다. 평가를 돌리려면 `03_수집_3년/`(원본·`정답셋_후보/정답_입력완.xlsx`)이 있는 폴더를 환경 변수 `LETS_DATA_ROOT`로 준다. 없으면 이 저장소의 상위 폴더를 본다
- **평가 결과(`eval/results/`)·시험 키트(`eval/data/`)·외부 검증 산출물(`eval/review/`)**: 원문 인용과 모델 출력이 들어 있어 넣지 않았다(`eval/.gitignore`). 문서에 이 경로가 나오면 로컬 기록을 가리킨다
- **설계 문서·트러블슈팅 기록**: 팀 규칙(`.gitignore`의 `docs/`, `*.md`)대로 저장소 밖에서 관리한다
- **API 키**: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` 환경 변수로만 받는다. 파일로 두지 않는다

## L3 평가 실행

```bash
python -X utf8 eval/run_l3_eval.py --primary gt                                      # 자체 점검: 정답이 전부 '맞음'
python -X utf8 eval/run_l3_eval.py --primary gt --verifier fake-wrong                # 교차 확인: 틀린 PENDING 0
python -X utf8 eval/run_l3_eval.py --primary claude-haiku-5-5 --verifier gpt-6-luna  # 실제 모델 (원문이 외부로 나감)
```

2026-11-26 실제 모델 결과 (프롬프트 l3-v3, 묶음 2,500, Haiku thinking 끔): 정답 167줄 중 맞음 23, 틀린 PENDING 0, 실패 호출 0 (호출 94회, 약 $0.10). 경위는 [l3_spec/README.md](l3_spec/README.md) '실제 모델 시험'.
