# A.X-4.0-Light vs EXAONE-3.5-7.8B 비교 (2026-11-09)

두 모델 모두 같은 train(2,820문장, 같은 train·val 분할), 같은 학습 시스템 프롬프트(sha256 `06818f0f…b556`),
같은 QLoRA 설정(4bit NF4, r=16, alpha=32, lr=2e-4, seed 42)으로 학습하고, val 완전 정확도가 가장 높은 epoch의 어댑터로
같은 dev 216문장과 test 240문장(md5 `a405dcd3…`)을 각각 한 번 평가했다. 채점은 영양소 2개·방향이 모두 맞아야 정답이다.

## 전체

| 평가 | A.X (finetune_v1) | EXAONE (finetune_v2) | 차이 | 짝 비교 |
|---|---|---|---|---|
| val (best epoch) | 234/270 = 86.7% (epoch 1) | 231/270 = 85.6% (epoch 3) | −1.1%p | 참고용 |
| dev 216 | 186/216 = 86.1% (80.9~90.1%) | 182/216 = 84.3% (78.8~88.5%) | −1.8%p | A.X만 15, EXAONE만 11, McNemar p=0.56 |
| test 240 | 206/240 = 85.8% (80.9~89.7%) | 212/240 = 88.3% (83.7~91.8%) | +2.5%p | A.X만 8, EXAONE만 14, McNemar p=0.29 |
| dev+test 456 | 392/456 = 86.0% | 394/456 = 86.4% | +0.4%p | |

괄호는 95% 구간(Wilson). 같은 상황의 문장끼리는 서로 비슷해서 실제 불확실성은 더 크다.
JSON 형식 오류, 영양소 개수 오류, 잘림은 두 모델 모두 dev·test에서 0건이다.

**결론: 두 모델의 정확도 차이는 통계적으로 구분되지 않는다(dev는 A.X, test는 EXAONE이 조금 높음).**

## test 상황별 (정답 수 / 20)

| 상황ID | 정답 쌍 | A.X | EXAONE |
|---|---|---|---|
| S018 | protein/high, fat/low | 18 | 18 |
| S036 | sodium/low, fat/low | 14 | 16 |
| S2009 | carbs/high, calories/high | 19 | 18 |
| S2036 | fat/low, calories/low | 19 | 17 |
| S2054 | calories/low, fat/low | 19 | 19 |
| S2063 | sugar/high, calories/high | 17 | 17 |
| S3001 | carbs/low, protein/high | 9 | 14 |
| S3002 | fat/high, calories/high | 20 | 19 |
| S3003 | calories/high, carbs/high | 17 | 18 |
| S3004 | calories/high, carbs/high | 16 | 17 |
| S3005 | sugar/low, calories/low | 20 | 20 |
| S3006 | sodium/high, sugar/high | 18 | 19 |

EXAONE의 test 우위는 대부분 S3001(+5)에서 나왔다.

## dev 상황별 (정답 수 / 전체)

| 상황ID | A.X | EXAONE | 전체 |
|---|---|---|---|
| S016 | 19 | 15 | 20 |
| S017 | 19 | 20 | 20 |
| S034 | 14 | 19 | 20 |
| S041 | 20 | 20 | 20 |
| S2008 | 4 | 5 | 17 |
| S2018 | 14 | 16 | 17 |
| S2027 | 17 | 17 | 17 |
| S2035 | 17 | 17 | 17 |
| S2045 | 14 | 5 | 17 |
| S2053 | 15 | 14 | 17 |
| S2062 | 16 | 17 | 17 |
| S2072 | 17 | 17 | 17 |

dev에서는 S2045(EXAONE −9)와 S034(EXAONE +5)처럼 상황별로 크게 엇갈린다.

## test 말투 유형별

| 말투 유형 | A.X | EXAONE |
|---|---|---|
| 구어체 | 43/50 | 45/50 |
| 길고 두서없는 문장 | 21/24 | 24/24 |
| 목적 직접형 | 35/36 | 35/36 |
| 성분 직접 언급 | 22/24 | 22/24 |
| 예산 포함 | 50/58 | 51/58 |
| 줄임말·오타 | 25/36 | 26/36 |
| 짧은 문장 | 10/12 | 9/12 |

## 같지 않은 조건

- **학습 중단**: A.X는 조기 종료 규칙(개선 없는 epoch 3번)으로 epoch 4에서 멈췄다. EXAONE은 사용자 요청으로 epoch 5 도중에 멈췄다(개선 없음 1/3 상태). best는 둘 다 val 기준으로 골랐으므로 test를 보고 고른 것은 아니지만, EXAONE은 epoch 5~6을 확인하지 않았다.
- **transformers 버전**: A.X 5.20.2, EXAONE 5.1.0(EXAONE 모델 코드가 이 버전에서만 동작). torch·peft·bitsandbytes는 같다.
- **토큰화**: EXAONE은 `[|assistant|]`가 일반 글자라 질문과 답을 따로 토큰화했다. 학습하는 글자는 같다.
- **평가 GPU**: A.X test는 RTX 4060(WSL), EXAONE은 RTX 4090(서버). 둘 다 4bit, greedy 생성이다.
- **test 사용 이력**: 이 test는 #28 프롬프트(앱 전용 규칙)를 정할 때 쓰였다. 위 평가는 두 모델 모두 학습 프롬프트로 했으므로 비교에는 영향이 없다.

## 실행 측면

| 항목 | A.X | EXAONE |
|---|---|---|
| 4bit 적재 메모리 | 약 4.95GiB | 약 4.92GiB |
| 문장당 생성 시간 (4090) | 약 0.9초 | 약 0.9초 |
| 앱(query_parser) 연결 | 완료 | 미확인 |
| 모델 코드 | transformers 기본 지원 | 모델에 딸린 코드(trust_remote_code), transformers 5.1.0 필요 |
| 라이선스 | | EXAONE AI Model License (비상업용) |
