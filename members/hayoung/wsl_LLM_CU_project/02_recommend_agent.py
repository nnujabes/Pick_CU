import pandas as pd

class NutritionRecommender:
    def __init__(self, csv_path="cleaned_nutrition_50.csv"):
        """
        1단계에서 정제한 CSV 파일을 로드합니다.
        """
        self.df = pd.read_csv(csv_path)
        print(f" 추천 데이터베이스 로드 완료! (총 {len(self.df)}개 상품 상주)")

    def recommend(self, category=None, max_price=None, min_protein=None, max_sodium=None, max_calories=None, top_k=3):
        """
        사용자의 요구 조건(가격, 영양성분)에 맞는 최적의 상품을 검색하여 추천합니다.
        """
        filtered_df = self.df.copy()

        # 1. 카테고리 필터링 (예: '간편식사', '샐러드' 등)
        if category:
            filtered_df = filtered_df[filtered_df['category_name'].str.contains(category, na=False) | 
                                      filtered_df['product_name'].str.contains(category, na=False)]

        # 2. 가격 조건
        if max_price:
            filtered_df = filtered_df[filtered_df['price'] <= max_price]

        # 3. 영양성분 조건 (1단계에서 만든 _num 컬럼 활용)
        if min_protein:
            filtered_df = filtered_df[filtered_df['단백질_num'] >= min_protein]
        if max_sodium:
            filtered_df = filtered_df[filtered_df['나트륨_num'] <= max_sodium]
        if max_calories:
            filtered_df = filtered_df[filtered_df['열량_num'] <= max_calories]

        if filtered_df.empty:
            return " 조건에 일치하는 편의점 상품을 찾지 못했습니다. 조건을 조금 다르게 설정해 보세요!"

        # 추천 결과 상위 top_k개 추출
        results = filtered_df.head(top_k)
        
        # 사용자 제공용 큐레이션 답변 생성 (챗봇 응답 포맷)
        response = f" 추천 결과 총 {len(results)}건의 상품을 찾았습니다:\n"
        response += "=" * 50 + "\n"
        
        for idx, row in results.iterrows():
            response += f"• [{row['product_name']}] - {row['price']:,}원\n"
            response += f"  - 열량: {row['열량_num']} kcal | 단백질: {row['단백질_num']} g | 나트륨: {row['나트륨_num']} mg\n"
        response += "=" * 50
        
        return response

if __name__ == "__main__":
    # 에이전트 생성
    agent = NutritionRecommender("cleaned_nutrition_50.csv")
    
    print("\n--- [테스트 1] 단백질 10g 이상, 5,000원 이하 상품 추천 ---")
    print(agent.recommend(min_protein=10.0, max_price=5000))

    print("\n--- [테스트 2] 나트륨 500mg 이하 저나트륨 상품 추천 ---")
    print(agent.recommend(max_sodium=500.0))