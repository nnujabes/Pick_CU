# convert.py
import pandas as pd
import json

df = pd.read_csv("sheet4.csv", encoding="utf-8-sig")
df.columns = ["sent_id", "situation_id", "text", "style", "nutrient", "direction"]

# 빈칸·오류 점검
bad = df[df.isna().any(axis=1) | df["nutrient"].astype(str).str.contains("#")]
print(f"전체 {len(df)}행, 문제 행 {len(bad)}행")
if len(bad):
    print(bad)

# 한글 -> 영문 코드 (LLM 출력 안정성을 위해)
nutrient_map = {"열량": "calories", "단백질": "protein", "나트륨": "sodium",
                "탄수화물": "carbs", "당류": "sugar", "지방": "fat"}
direction_map = {"높음": "high", "낮음": "low"}

df = df.dropna()
df["nutrient"] = df["nutrient"].map(nutrient_map)
df["direction"] = df["direction"].map(direction_map)
assert df[["nutrient", "direction"]].notna().all().all(), "매핑 안 된 값이 있어요"

SYSTEM = ("사용자의 편의점 식품 요청을 읽고, 가장 중요한 영양 성분 1개와 방향(high/low)을 "
          "JSON으로만 출력하세요. 성분: calories, protein, sodium, carbs, sugar, fat")

def to_record(row):
    return {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": row["text"]},
        {"role": "assistant",
         "content": json.dumps({"nutrient": row["nutrient"], "direction": row["direction"]},
                               ensure_ascii=False)},
    ]}

# 상황 단위로 학습/평가 분리 (같은 상황이 양쪽에 섞이지 않게)
sit_ids = sorted(df["situation_id"].unique())
eval_ids = set(sit_ids[7::5])        # 약 20%를 평가용 상황으로 (임시 규칙)
train = df[~df["situation_id"].isin(eval_ids)]
test = df[df["situation_id"].isin(eval_ids)]

for name, part in [("train", train), ("eval", test)]:
    with open(f"{name}.jsonl", "w", encoding="utf-8") as f:
        for _, r in part.iterrows():
            f.write(json.dumps(to_record(r), ensure_ascii=False) + "\n")
    print(name, len(part))