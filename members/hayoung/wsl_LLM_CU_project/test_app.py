import json
import ollama
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="편의점 큐레이터", page_icon="🏪", layout="wide")

# 타이틀 및 안내
st.title("🏪 편의점 큐레이터")
st.caption(
    "사용자의 목적과 예산에 딱 맞는 최적의 편의점 조합을 추천해 드립니다."
)

# ---------------------------------------------------------
# 세션 상태(Memory) 초기화
# ---------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "reviews" not in st.session_state:
    # 시연용 기본 사전 작성 리뷰
    st.session_state["reviews"] = {
        "혜자로운 제육도시락 + 훈제란 2입": [
            {
                "rating": 5,
                "comment": "운동하고 먹었는데 단백질 든든해서 너무 좋네요!",
            },
            {"rating": 4, "comment": "가성비 최고 조합입니다."},
        ]
    }

# ---------------------------------------------------------
# 사이드바 (카테고리 선택 + 빠른 시연 키워드 + 누적 리뷰)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 1. 카테고리 선택")
    selected_categories = st.multiselect(
        "검색할 제품 카테고리를 고르세요",
        ["식사류", "사이드류", "디저트류", "음료류"],
        default=["식사류", "사이드류", "디저트류", "음료류"],
    )

    st.markdown("---")
    st.header("💡 2. 빠른 시연 키워드")
    if st.button("🏋️ 운동 후 단백질 (1만원)"):
        st.session_state["prompt_trigger"] = (
            "운동 후 단백질 보충할 음식을 10,000원 이내에서 추천해줘"
        )
    if st.button("🌙 야식 안 붓는 거 (6천원)"):
        st.session_state["prompt_trigger"] = (
            "야식을 먹고 싶은데 내일 아침 얼굴 안 붓는 음식으로 6,000원 이내에서 추천해줘"
        )
    if st.button("❓ 모호한 질문 테스트"):
        st.session_state["prompt_trigger"] = "맛있는 거 아무거나 추천해줘"

    st.markdown("---")
    st.subheader("📝 전체 누적 리뷰")
    if not st.session_state["reviews"]:
        st.write("아직 등록된 리뷰가 없습니다.")
    else:
        for combo_name, r_list in st.session_state["reviews"].items():
            st.write(f"**[{combo_name}]**")
            for r in r_list:
                st.caption(f"⭐ {r['rating']}점 - {r['comment']}")

# ---------------------------------------------------------
# 1. 이전 대화 기록 화면 출력
# ---------------------------------------------------------
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        if msg["type"] == "text":
            st.write(msg["content"])
        elif msg["type"] == "recommendation":
            card_data = msg["content"]
            st.success(
                f"🎯 **분석된 조건:** 선택 카테고리 ({', '.join(card_data['categories'])}) | 최대 예산 {card_data['max_price']}원 | 강조 영양: {card_data['nutrition_focus']}"
            )

            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"🏆 1위 조합: {card_data['combo_name']}")
                    st.write(f"💡 **AI 추천 이유:** {card_data['reason']}")
                    st.caption(
                        f"📊 영양 정보: 단백질 {card_data['protein']}g | 나트륨 {card_data['sodium']}mg"
                    )
                with col2:
                    st.metric("총 금액", f"{card_data['price']:,}원")
                    st.write(f"⭐ 평균 평점: ★ {card_data['avg_rating']:.1f}")

            # 리뷰 영역 표시
            st.markdown("##### 💬 이 조합의 등록된 리뷰")
            reviews = st.session_state["reviews"].get(
                card_data["combo_name"], []
            )
            if reviews:
                for r in reviews:
                    st.text(f"⭐ {r['rating']}점 | {r['comment']}")
            else:
                st.caption("아직 작성된 리뷰가 없습니다.")

# ---------------------------------------------------------
# 2. 신규 사용자 입력 처리
# ---------------------------------------------------------
user_input = st.chat_input(
    "선택한 카테고리 내에서 원하는 음식 조건이나 추가 질문을 입력하세요..."
)
button_prompt = st.session_state.pop("prompt_trigger", None)

if button_prompt:
    user_input = button_prompt

if user_input:
    # 사용자 입력 대화 기록 저장 및 화면 표시
    st.session_state["messages"].append(
        {"role": "user", "type": "text", "content": user_input}
    )

    # 1차 LLM: JSON 해석
    with st.spinner("AI가 요청을 해석하고 최적의 조합을 계산 중입니다..."):
        system_prompt_extract = f"""
        너는 편의점 상품 추천 시스템의 '사용자 요청 해석기'야. 
        사용자의 입력에서 조건(예산, 영양 목표)을 추출해서 오직 지정된 JSON 형식으로만 응답해.

        [선택된 카테고리]
        {', '.join(selected_categories) if selected_categories else "전체"}

        [영양 목표 종류]
        - "protein": 단백질, 운동, 근육 관련
        - "low_sodium": 나트륨, 부기, 야식, 덜 짜게 관련
        - "none": 별도 영양 조건 없음

        [need_more_info 판단 기준]
        - 예산(max_price)이나 구체적인 조건이 전혀 없어서 추천 방향을 잡기 어려울 때만 true
        - 예산이나 영양 목표 중 하나라도 명확히 제시되어 있으면 false

        [출력 규칙]
        - 입력에 금액/예산이 언급되지 않았으면 max_price는 null로 출력해.
        - 오직 valid한 JSON만 출력해.
        """

        try:
            response_extract = ollama.chat(
                model="llama3.2:3b",
                messages=[
                    {"role": "system", "content": system_prompt_extract},
                    {"role": "user", "content": user_input},
                ],
                format="json",
            )
            parsed_json = json.loads(response_extract["message"]["content"])
        except Exception as e:
            parsed_json = {
                "max_price": None,
                "nutrition_focus": "none",
                "need_more_info": True,
            }

        need_more_info = parsed_json.get("need_more_info", False)
        max_price = parsed_json.get("max_price")
        nutrition_focus = parsed_json.get("nutrition_focus", "none")

        # 재질의 케이스
        if need_more_info:
            guide_msg = "💬 예산이나 원하시는 조건(단백질, 안 붓는 야식 등)을 조금 더 자세히 말씀해 주시면 딱 맞는 조합을 찾아드릴게요!"
            st.session_state["messages"].append(
                {"role": "assistant", "type": "text", "content": guide_msg}
            )

        # 추천 실행 케이스
        else:
            dummy_db = [
                {
                    "id": 1,
                    "name": "혜자로운 제육도시락",
                    "category": "식사류",
                    "price": 4500,
                    "protein": 22,
                    "sodium": 890,
                },
                {
                    "id": 2,
                    "name": "훈제란 2입",
                    "category": "사이드류",
                    "price": 2200,
                    "protein": 12,
                    "sodium": 210,
                },
                {
                    "id": 3,
                    "name": "저당 고단백 두유",
                    "category": "음료류",
                    "price": 1800,
                    "protein": 10,
                    "sodium": 110,
                },
                {
                    "id": 4,
                    "name": "매콤 떡볶이",
                    "category": "식사류",
                    "price": 3800,
                    "protein": 6,
                    "sodium": 1250,
                },
                {
                    "id": 5,
                    "name": "초코 롤케이크",
                    "category": "디저트류",
                    "price": 2500,
                    "protein": 3,
                    "sodium": 180,
                },
            ]

            # 카테고리 필터링 적용
            filtered_db = (
                [
                    item
                    for item in dummy_db
                    if item["category"] in selected_categories
                ]
                if selected_categories
                else dummy_db
            )

            recommended_combinations = []
            for i in range(len(filtered_db)):
                for j in range(i + 1, len(filtered_db)):
                    item1, item2 = filtered_db[i], filtered_db[j]
                    total_price = item1["price"] + item2["price"]
                    total_protein = item1["protein"] + item2["protein"]
                    total_sodium = item1["sodium"] + item2["sodium"]

                    if max_price is None or total_price <= max_price:
                        recommended_combinations.append({
                            "items": [item1["name"], item2["name"]],
                            "total_price": total_price,
                            "total_protein": total_protein,
                            "total_sodium": total_sodium,
                        })

            if not recommended_combinations:
                no_res_msg = "⚠️ 선택하신 카테고리와 예산 내에서 조건에 맞는 조합을 찾지 못했습니다. 카테고리를 확장하거나 예산을 늘려보세요!"
                st.session_state["messages"].append(
                    {
                        "role": "assistant",
                        "type": "text",
                        "content": no_res_msg,
                    }
                )
            else:
                if nutrition_focus == "protein":
                    recommended_combinations.sort(
                        key=lambda x: x["total_protein"], reverse=True
                    )
                elif nutrition_focus == "low_sodium":
                    recommended_combinations.sort(
                        key=lambda x: x["total_sodium"]
                    )

                top1 = recommended_combinations[0]
                combo_name = " + ".join(top1["items"])

                # 2차 LLM: 추천 이유 생성 (exaone 사용)
                top1_info_text = f"- 추천 조합: {combo_name}\n- 총 가격: {top1['total_price']}원\n- 총 단백질: {top1['total_protein']}g\n- 총 나트륨: {top1['total_sodium']}mg"
                system_prompt_reason = "너는 친절한 편의점 식품 큐레이터야. 제시된 정보만으로 자연스러운 한국어 1~2문장 추천 사유를 작성해줘. 새로운 수치는 지어내지 마."

                try:
                    response_reason = ollama.chat(
                        model="exaone3.5:latest",
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt_reason,
                            },
                            {
                                "role": "user",
                                "content": f"[질문]: {user_input}\n[조합]:\n{top1_info_text}",
                            },
                        ],
                    )
                    ai_reason_text = response_reason["message"]["content"]
                except Exception as e:
                    ai_reason_text = f"목표 조건을 만족하는 가성비 최적 조합입니다. (총 금액: {top1['total_price']:,}원)"

                combo_reviews = st.session_state["reviews"].get(combo_name, [])
                avg_rating = (
                    sum(r["rating"] for r in combo_reviews)
                    / len(combo_reviews)
                    if combo_reviews
                    else 5.0
                )

                card_payload = {
                    "combo_name": combo_name,
                    "price": top1["total_price"],
                    "protein": top1["total_protein"],
                    "sodium": top1["total_sodium"],
                    "reason": ai_reason_text,
                    "max_price": max_price if max_price else "자유",
                    "nutrition_focus": nutrition_focus,
                    "categories": (
                        selected_categories if selected_categories else ["전체"]
                    ),
                    "avg_rating": avg_rating,
                }

                st.session_state["messages"].append(
                    {
                        "role": "assistant",
                        "type": "recommendation",
                        "content": card_payload,
                    }
                )

    # 화면 즉시 갱신
    st.rerun()

# ---------------------------------------------------------
# 3. 하단 리뷰 입력 폼
# ---------------------------------------------------------
st.markdown("---")
with st.expander("📝 구매한 추천 조합에 리뷰 남기기"):
    with st.form("review_form", clear_on_submit=True):
        target_combo = st.selectbox(
            "리뷰를 남길 조합 선택",
            [
                "혜자로운 제육도시락 + 훈제란 2입",
                "혜자로운 제육도시락 + 저당 고단백 두유",
                "매콤 떡볶이 + 초코 롤케이크",
            ],
        )
        new_rating = st.slider("별점", 1, 5, 5)
        new_comment = st.text_input("한 줄 후기를 작성해 주세요")
        submit_btn = st.form_submit_button("리뷰 등록하기")

        if submit_btn and new_comment:
            if target_combo not in st.session_state["reviews"]:
                st.session_state["reviews"][target_combo] = []

            st.session_state["reviews"][target_combo].append(
                {"rating": new_rating, "comment": new_comment}
            )
            st.success(f"'{target_combo}' 조합에 리뷰가 등록되었습니다!")
            st.rerun()