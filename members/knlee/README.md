# knlee

## 담당 역할

모델 개발, DB 연동. CU 상품 데이터 수집과 영양성분표 이미지의 영양소 추출을 맡았습니다.

## 이 폴더가 하는 일

CU 상품 정보와 영양성분표 이미지를 수집하고, 이미지에서 영양소 6개를 추출합니다.

| 파일 | 역할 |
| --- | --- |
| `crawl_cu.py` | 카테고리별 수집 실행 프로그램 |
| `crawl_cu_core.py` | 수집에 쓰는 공통 기능. `crawl_cu.py`가 불러서 사용 |
| `vlm_nutrition_parser.py` | Qwen2.5-VL로 영양소를 추출하고 검증해 `products.csv`에 반영 |

영양소는 열량, 나트륨, 탄수화물, 당류, 지방, 단백질입니다. 추출 결과는 DB 포함, 검수 필요, 성분 누락, 영양표 없음, 실패로 분류합니다.

저장된 이미지 3,873건에서 2,154개 상품을 DB에 넣었습니다(55.6%).

이미지와 모델은 저장소에 없습니다. 파서로 추론하려면 이미지와 `Qwen2.5-VL-7B` 모델이 있어야 합니다.

## 실행 방법

```bash
# 수집: 결과는 스크립트 옆의 cu_output/ 에 저장
python crawl_cu.py --categories 1 2                                  # 일반 다운로드
python crawl_cu.py --categories 1 2 3 4 5 6 --list-only --refresh-list  # 가격과 행사 정보만 다시 수집

# 영양소 추출: --base-dir에 cu_output 폴더를 지정
python vlm_nutrition_parser.py --self-check                          # 모델 없이 검증 코드 점검
python vlm_nutrition_parser.py --categories 01_간편식사 --limit 10     # 일부만 시험
python vlm_nutrition_parser.py --load-in-4bit                        # 8GB GPU용 4-bit 양자화
python vlm_nutrition_parser.py --apply                               # 추론 후 products.csv 반영
python vlm_nutrition_parser.py --apply-only                          # 저장된 결과 CSV만 반영
```

RTX 4090(bf16) 기준 이미지당 약 4초, 최대 VRAM 약 16GB가 걸렸습니다. 수집과 추출은 끝난 작업이라 다시 실행할 일은 많지 않습니다.

## 핵심 함수

다른 팀원이 호출할 함수는 없습니다. 파서의 주요 함수는 다음과 같습니다.

| 이름 | 입력 | 출력 | 예시 |
| --- | --- | --- | --- |
| `build_result` | 모델 원문 | 정리하고 검증한 결과 | `build_result(raw_output)` |
| `classify_result` | 결과, 상품명 | 분류 결과 | `classify_result(result, product_name)` |
| `self_check` | 없음 | 없음(실패 시 오류) | `self_check()` |

## 필요한 라이브러리

Python 3.12.15에서 사용한 버전입니다.

- 수집: `requests==2.34.2`, `beautifulsoup4==4.15.0`
- 영양소 추출: `pandas==2.3.3`, `pillow==12.3.0`, `torch==2.14.0`, `transformers==5.17.0`, `accelerate==1.15.0`, `bitsandbytes==0.50.2`, `qwen-vl-utils==0.0.14`

## 통합 때 옮길 위치

서비스 실행에는 쓰지 않으므로 이 폴더에 그대로 둡니다. 검색 함수와 필터 엔진의 위치는 팀에서 폴더 구조를 정한 뒤 적습니다.
