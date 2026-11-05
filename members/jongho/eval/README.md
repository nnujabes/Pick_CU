# A.X 파인튜닝 모델 평가

파인튜닝한 A.X-4.0-Light 어댑터가 문장에서 영양소 2개와 방향을 맞히는지 평가합니다. 채점과 저장은 `members/hayoung/finetune_v1/code`의 기존 코드를 그대로 쓰므로 dev 결과와 같은 기준으로 비교할 수 있습니다.

**test 데이터는 git에 올리지 않습니다.** 평가할 때 담당자(jongho)에게 따로 받으세요.

## 파일

| 파일 | 내용 |
| --- | --- |
| `run_eval.py` | 평가 함수와 실행 명령 |
| `results/dev_4060/` | 비교 기준이 되는 dev 결과 |

## 실행 전 준비

명령은 모두 저장소 루트에서 실행합니다.

| 항목 | 조건 |
| --- | --- |
| GPU | NVIDIA, 메모리 약 5GB 이상 (RTX 4060 8GB에서 최대 4.95GiB 사용) |
| 원본 모델 | `skt/A.X-4.0-Light`. 첫 실행 때 허깅페이스에서 자동으로 받음 (약 15GB) |
| 어댑터 | `adapter_model.safetensors`. git에 없어 따로 받아서 `members/hayoung/finetune_v1/adapter/best/`에 넣음 |

1. torch를 PC의 CUDA 버전에 맞게 먼저 설치합니다.
2. 나머지 패키지를 설치합니다. Windows에서는 `bitsandbytes` 설치가 어려울 수 있습니다.

    ```bash
    pip install -r members/hayoung/finetune_v1/requirements.txt
    ```

3. 어댑터 파일이 맞는지 확인합니다.

    ```bash
    sha256sum members/hayoung/finetune_v1/adapter/best/adapter_model.safetensors
    # f95d9f5e429f0f16c854c769253ee0dd4df075f91b5ea3cc29fd56b7b157cc8b
    ```

## 실행

먼저 dev를 돌려 186/216이 나오는지 확인합니다. RTX 4060에서 약 12분 걸립니다.

```bash
python members/jongho/eval/run_eval.py members/hayoung/dev_pair_v3_baseline/dev_pair_v3.csv members/jongho/eval/results/dev_new
```

test는 따로 받은 CSV를 이 폴더에 두고 실행합니다. 결과 폴더 이름은 `results/test`로 시작해야 git에 올라가지 않습니다.

```bash
python members/jongho/eval/run_eval.py members/jongho/eval/test_pair_v3_240.csv members/jongho/eval/results/test
```

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--adapter 경로` | `members/hayoung/finetune_v1/adapter/best` | 어댑터 폴더 |
| `--exclude ID ...` | `S3003` | 제외 정답률을 따로 계산할 상황. 값 없이 `--exclude`만 쓰면 계산하지 않음. CSV에 없는 상황이면 무시 |

코드에서 부를 때는 `members/jongho/eval`을 import 경로에 넣고 다음과 같이 씁니다.

```python
from run_eval import run_eval

report = run_eval("입력.csv", "결과_폴더")
```

## 입력 CSV 형식

UTF-8 CSV이고 다음 열이 필요합니다. 빈 행이 있으면 읽다가 오류가 납니다. 모델에는 `입력 문장`만 들어갑니다.

```text
상황ID,입력 문장,말투 유형,작성자,성분1,방향1,성분2,방향2
```

- 성분: `열량`, `단백질`, `나트륨`, `탄수화물`, `당류`, `지방`
- 방향: `높음`, `낮음`

## 결과 파일

| 파일 | 내용 |
| --- | --- |
| `report.json` | 전체, 라벨 짝별, 지정 상황 제외 정답률과 95% 구간 |
| `summary.json` | 성분별, 방향별, 상황별, 말투별 세부 지표와 입력 파일 해시 |
| `rows.csv` | 문장별 정답, 예측, 결과, 모델 원문 출력 |
| `wrong.csv` | 틀린 문장만 |

- **완전 정답:** 영양소와 방향 두 쌍을 모두 맞힌 경우입니다. 순서는 보지 않습니다.
- **95% 구간:** 문장을 서로 독립으로 보고 계산합니다. 같은 상황의 문장은 함께 맞거나 틀리기 쉬워서 실제 불확실성은 더 큽니다.

## 주의 사항

- **test 결과를 보고 모델이나 프롬프트를 고치지 마세요.** 고치면 깨끗한 수치가 아닙니다.
- **test 데이터와 test 결과를 커밋하지 마세요.** 결과의 `rows.csv`에도 test 문장이 들어 있습니다.
- **결과 폴더가 이미 있으면 실행하지 않습니다.** 결과를 덮어쓰거나 실수로 다시 돌리는 일을 막기 위한 것입니다.

## 확인한 결과

2026-11-05에 WSL, RTX 4060 8GB에서 dev로 확인했습니다. test는 아직 평가하지 않았습니다.

| 항목 | 결과 |
| --- | --- |
| dev 완전 정답률 | 186/216 = 86.1% (서버 기록과 동일) |
| 서버 출력과 비교 | 216문장 모두 글자까지 동일 |
| 형식 오류, 출력 잘림 | 0건 |
| 소요 시간 | 722초 (문장당 약 3.3초) |
| 환경 | Python 3.12.3, torch 2.15.0, transformers 5.22.1, peft 0.21.2, bitsandbytes 0.50.2 |

이 기록은 저장소로 옮기기 전 폴더 구조에서 돌린 것입니다.
