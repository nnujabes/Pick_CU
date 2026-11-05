import json
import ollama
import chainlit as cl

# 1. 시연용 확장 Dummy DB (카테고리별 상품)
DUMMY_DB = [
    {"id": 1, "name": "혜자로운 제육도시락", "category": "식사류", "price": 4500, "protein": 22, "sodium": 890},
    {"id": 2, "name": "훈제란 2입", "category": "사이드류", "price": 2200, "protein": 12, "sodium": 210},
    {"id": 3, "name": "저당 고단백 두유", "category": "음료류", "price": 1800, "protein": 10, "sodium": 110},
    {"id": 4, "name": "매콤 떡볶이", "category": "식사류", "price": 3800, "protein": 6, "sodium": 1250},
    {"id": 5, "name": "초코 롤케이크", "category": "디저트류", "price": 2500, "protein": 3, "sodium": 180},
    {"id": 6, "name": "아메리카노 헤이즐넛", "category": "음료류", "price": 2000, "protein": 1, "sodium": 15},
    {"id": 7, "name": "프로틴 제로 스파클링", "category": "음료류", "price": 2300, "protein": 15, "sodium": 45},
    {"id": 8, "name": "닭가슴살 소세지", "category": "사이드류", "price": 2000, "protein": 18, "sodium": 350},
]


@cl.on_chat_start
async def start():
    welcome_message = """
🏪 **편의점 큐레이터에 오신 것을 환영합니다!**

원하시는 카테고리(음료만, 식사류 등)나 예산, 영양 목표를 자유롭게 말씀해 주세요!
조건에 맞는 **TOP 5 최적 추천 조합**을 찾아드립니다.

*예시:*
- *"음료만 5,000원 이내로 추천해줘"*
- *"운동 후 단백질 보충할 음식 10,000원 이내로 추천해줘"*
"""
    await cl.Message(content=welcome_message).send()


@cl.on_message
async def main(message: cl.Message):
    user_input = message.content

    # --- Step 1: 1차 LLM (요청 조건 해석) ---
    async with cl.Step(name="🔍 사용자 요청 분석 중...") as step:
        system_prompt_extract = """
        너는 편의점 상품 추천 시스템의 '사용자 요청 해석기'야. 
        사용자의 입력에서 조건(카테고리, 예산, 영양 목표)을 추출해서 오직 지정된 JSON 형식으로만 응답해.

        [카테고리 종류]
        식사류, 사이드류, 디저트류, 음료류

        [영양 목표 종류]
        - "protein": 단백질, 운동, 근육 관련
        - "low_sodium": 나트륨, 부기, 야식, 덜 짜게 관련
        - "none": 별도 영양 조건 없음

        [need_more_info 판단 기준]
        - 예산(max_price), 카테고리, 구체적인 조건이 전혀 없어서 추천 방향을 잡기 어려울 때만 true
        - 카테고리, 예산, 영양 목표 중 하나라도 언급되어 있으면 false

        [출력 JSON 양식]
        {
          "categories": ["언급된 카테고리 목록 (없으면 빈 리스트 [])"],
          "max_price": 숫자 또는 null,
          "nutrition_focus": "protein" 또는 "low_sodium" 또는 "none",
          "need_more_info": true 또는 false
        }
        """

        response_extract = ollama.chat(
            model="llama3.2:3b",
            messages=[
                {"role": "system", "content": system_prompt_extract},
                {"role": "user", "content": user_input},
            ],
            format="json",
        )
        parsed_json = json.loads(response_extract["message"]["content"])

        categories = parsed_json.get("categories", [])
        max_price = parsed_json.get("max_price")
        nutrition_focus = parsed_json.get("nutrition_focus", "none")
        need_more_info = parsed_json.get("need_more_info", False)

        step.output = f"파싱 결과: 카테고리={categories}, 예산={max_price}원, 영양목표={nutrition_focus}"

    if need_more_info:
        await cl.Message(
            content="💬 원하시는 카테고리(음료, 식사 등)나 예산을 조금 더 자세히 말씀해 주시면 딱 맞는 상품을 찾아드릴게요!"
        ).send()
        return

    # --- Step 2: 파이썬 필터링 & 단일/조합 탐색 ---
    async with cl.Step(name="📊 DB 기반 수치 계산 및 TOP 5 검색 중...") as step:
        # 1) 카테고리 필터링
        if categories:
            filtered_db = [item for item in DUMMY_DB if item["category"] in categories]
        else:
            filtered_db = DUMMY_DB

        candidates = []

        # 2) 단일 제품 후보 추가
        for item in filtered_db:
            if max_price is None or item["price"] <= max_price:
                candidates.append({
                    "items": [item["name"]],
                    "total_price": item["price"],
                    "total_protein": item["protein"],
                    "total_sodium": item["sodium"],
                })

        # 3) 2개 조합 후보 추가
        for i in range(len(filtered_db)):
            for j in range(i + 1, len(filtered_db)):
                item1, item2 = filtered_db[i], filtered_db[j]
                total_price = item1["price"] + item2["price"]
                if max_price is None or total_price <= max_price:
                    candidates.append({
                        "items": [item1["name"], item2["name"]],
                        "total_price": total_price,
                        "total_protein": item1["protein"] + item2["protein"],
                        "total_sodium": item1["sodium"] + item2["sodium"],
                    })

        if not candidates:
            step.output = "조건에 맞는 상품 없음"
            cat_str = ", ".join(categories) if categories else "전체"
            await cl.Message(
                content=f"⚠️ 선택하신 카테고리({cat_str}) 및 예산({f'{max_price:,}원' if max_price else '제한없음'}) 내에서 조건에 맞는 상품을 찾지 못했습니다."
            ).send()
            return

        # 4) 정렬 로직 (영양 목표별 정렬)
        if nutrition_focus == "protein":
            candidates.sort(key=lambda x: x["total_protein"], reverse=True)
        elif nutrition_focus == "low_sodium":
            candidates.sort(key=lambda x: x["total_sodium"])
        else:
            candidates.sort(key=lambda x: x["total_protein"], reverse=True)

        # 5) 상위 최대 5개 추출 (TOP 5)
        top_candidates = candidates[:5]
        step.output = f"TOP {len(top_candidates)} 조합 추출 완료"

    # --- Step 3: 2차 LLM (TOP 5 추천 이유 작성) ---
    async with cl.Step(name="💡 AI 큐레이터 총평 작성 중...") as step:
        # TOP 1위 상품 정보 기반으로 큐레이터 총평 작성
        top1 = top_candidates[0]
        top1_combo_name = " + ".join(top1["items"])
        
        top1_info_text = f"- 1위 조합: {top1_combo_name}\n- 가격: {top1['total_price']}원\n- 단백질: {top1['total_protein']}g\n- 나트륨: {top1['total_sodium']}mg"
        system_prompt_reason = "너는 친절한 편의점 식품 큐레이터야. 1위로 추천된 상품/조합 정보를 바탕으로 왜 이 추천이 최적인지 자연스러운 한국어 1~2문장으로 총평을 작성해줘. 새로운 수치는 지어내지 마."

        response_reason = ollama.chat(
            model="exaone3.5:latest",
            messages=[
                {"role": "system", "content": system_prompt_reason},
                {
                    "role": "user",
                    "content": f"[사용자 질문]: {user_input}\n[1위 추천 정보]:\n{top1_info_text}",
                },
            ],
        )
        ai_reason_text = response_reason["message"]["content"]
        step.output = "총평 작성 완료"

    # --- Step 4: 최종 TOP 5 카드 출력 ---
    final_card = f"### 🎯 TOP {len(top_candidates)} 추천 목록\n\n"
    
    for idx, c in enumerate(top_candidates, 1):
        combo_title = " + ".join(c["items"])
        final_card += f"**{idx}위. {combo_title}**\n"
        final_card += f"- 💰 가격: `{c['total_price']:,}원` | 📊 단백질: `{c['total_protein']}g` | 나트륨: `{c['total_sodium']}mg`\n\n"

    final_card += f"---\n💡 **AI 큐레이터 총평**\n{ai_reason_text}"

    await cl.Message(content=final_card).send()