import pandas as pd
import re

def parse_nutrition_value(val):
    """
    "197 kcal", "1,440mg", "4.41g", "1g 미만" 등의 텍스트를 숫자(float)로 변환합니다.
    % 단독 수치나 결측치는 None(NaN)으로 안전하게 처리합니다.
    """
    if pd.isna(val) or val is None:
        return None
    
    val_str = str(val).strip()
    
    # % 기호만 포함되고 g, mg, kcal 단위가 없는 오추출 텍스트 방어
    if '%' in val_str and not re.search(r'(g|mg|kcal)', val_str, re.IGNORECASE):
        return None
    
    # 천 단위 쉼표 제거 (예: 1,440mg -> 1440mg)
    val_str = val_str.replace(',', '')
    
    # "1g 미만" 같은 예외 규격 처리 (수치 절반값 또는 0.5로 정규화)
    if "미만" in val_str:
        match = re.search(r'(\d+(?:\.\d+)?)', val_str)
        return float(match.group(1)) / 2.0 if match else 0.5
        
    # 수치 범위 표기 (예: 3.0~5.8 kcal) 처리
    if "~" in val_str:
        numbers = re.findall(r'(\d+(?:\.\d+)?)', val_str)
        if len(numbers) >= 2:
            return (float(numbers[0]) + float(numbers[1])) / 2.0

    # 일반 수치 추출 (예: 630mg -> 630.0)
    match = re.search(r'(\d+(?:\.\d+)?)', val_str)
    if match:
        return float(match.group(1))
    
    return None

def run_pipeline(input_csv="nutrition_vlm_results_01.csv", output_csv="cleaned_nutrition_50.csv"):
    df = pd.read_csv(input_csv)
    print(f"원본 데이터 로드 완료: {len(df)}개 행")
    
    # 6대 영양성분 파싱
    target_cols = ['열량', '단백질', '나트륨', '탄수화물', '당류', '지방']
    for col in target_cols:
        if col in df.columns:
            df[f"{col}_num"] = df[col].apply(parse_nutrition_value)
            
    # 정제 완료 파일 저장 (한글 깨짐 방지 utf-8-sig)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"정제 파이프라인 실행 완료! 저장된 파일: {output_csv}\n")
    
    # 정제 결과 확인
    print("=== 정제된 주요 숫자 컬럼 예시 (상위 5개) ===")
    sample_cols = ['product_name', 'price', '열량_num', '단백질_num', '나트륨_num']
    print(df[sample_cols].head())
    
    return df

if __name__ == "__main__":
    run_pipeline()