"""v2 → v3: 비열량 상황의 "가볍게·순한" 음식 표현을 상황 단서로 교체 (라벨 불변).
usage: python make_v3.py <dev_v2> <train_v2> <out_dir>
출력: dev_pair_v3.csv, train_pair_v3.csv, 수정내역_v3.csv, 애매_목록_v3.csv, v3_check.json
입력 파일은 읽기만 함. 검증 하나라도 실패하면 exit 1.
"""
import collections
import csv
import hashlib
import json
import os
import re
import sys

PAT = re.compile("가볍|가벼|순한|순하|순해")
COLS = ["상황ID", "입력 문장", "말투 유형", "작성자", "성분1", "방향1", "성분2", "방향2"]
LABELS = ["성분1", "방향1", "성분2", "방향2"]
RULE_SITS = ["S001", "S019", "S2014", "S2046", "S2042", "S2001", "S2056", "S2065", "S2024", "S2030"]

# (세트, 0-based 데이터 행 번호): (이전 문장, 수정 문장, 바뀐 표현)
EDITS = {
    # dev S034 나트륨↓+지방↓
    ("dev", 42): ("어제 술이랑 고기 먹었더니 오늘은 순한 게 땡겨", "어제 술이랑 고기 먹었더니 오늘은 짜지 않은 게 땡겨", "순한 → 짜지 않은"),
    ("dev", 44): ("어제 늦게까지 마셨는데 오늘은 가볍게 먹고 싶어", "어제 늦게까지 마셨는데 오늘은 싱겁게 먹고 싶어", "가볍게 → 싱겁게"),
    ("dev", 45): ("회식으로 짜고 기름진 음식을 먹은 몸을 순하게 달래고 싶어", "회식으로 짜고 기름진 음식을 먹은 몸을 담백하게 달래고 싶어", "순하게 → 담백하게"),
    ("dev", 46): ("어제 과하게 먹은 걸 오늘은 가볍게 만회하는 식사를 하고 싶어", "어제 과하게 먹은 걸 오늘은 짜지 않게 만회하는 식사를 하고 싶어", "가볍게 → 짜지 않게"),
    ("dev", 47): ("회식 뒤라 몸이 부은 느낌이라 가볍게 비워주는 걸 먹고 싶어", "회식 뒤라 몸이 부은 느낌이라 싱겁게 붓기 빼주는 걸 먹고 싶어", "가볍게 비워주는 → 싱겁게 붓기 빼주는"),
    ("dev", 50): ("어제 회식 달림ㅠ 순한거 추천점", "어제 회식 달림ㅠ 안짠거 추천점", "순한거 → 안짠거"),
    ("dev", 54): ("어제 회식해서 4천원 안쪽으로 순한 거 골라줘", "어제 회식해서 4천원 안쪽으로 짜지 않은 거 골라줘", "순한 → 짜지 않은"),
    ("dev", 56): ("3천원대로 가벼운 아침 알려줘", "3천원대로 담백한 아침 알려줘", "가벼운 → 담백한"),
    ("dev", 57): ("어제 부서 회식에서 삼겹살에 소주에 찌개까지 먹었는데 오늘 아침에 일어났더니 얼굴이 퉁퉁 붓고 속도 안 좋아서 편의점에서 순하게 먹을 수 있는 걸 사고 싶어",
                  "어제 부서 회식에서 삼겹살에 소주에 찌개까지 먹었는데 오늘 아침에 일어났더니 얼굴이 퉁퉁 붓고 속도 안 좋아서 편의점에서 싱겁게 먹을 수 있는 걸 사고 싶어", "순하게 → 싱겁게"),
    ("dev", 58): ("회식이 새벽까지 이어져서 자고 일어났더니 입안이 텁텁하고 몸이 무거운데 점심은 편의점에서 해결해야 하니까 속 편하고 가벼운 걸로 추천해줘",
                  "회식이 새벽까지 이어져서 자고 일어났더니 입안이 텁텁하고 몸이 무거운데 점심은 편의점에서 해결해야 하니까 속 편하고 짜지 않은 걸로 추천해줘", "가벼운 → 짜지 않은"),
    # train 단백질↑+지방↓
    ("train", 87): ("회사 다니면서 다이어트하느라 점심은 가볍게 먹는데 저녁 운동 전후에 근육이 안 빠지게 뭘 챙기면 좋을지 모르겠어",
                    "회사 다니면서 다이어트하느라 점심은 단백질 위주로 먹는데 저녁 운동 전후에 근육이 안 빠지게 뭘 챙기면 좋을지 모르겠어", "가볍게 → 단백질 위주로"),
    ("train", 99): ("포만감이 오래 가는 닭가슴살 같은 가벼운 식사를 하고 싶어", "포만감이 오래 가는 닭가슴살 같은 단백질 있는 식사를 하고 싶어", "가벼운 → 단백질 있는"),
    ("train", 102): ("먹고 나서도 한참 배부른 계란이나 두부 쪽 가벼운 식사가 필요해", "먹고 나서도 한참 배부른 계란이나 두부 쪽 단백질 식사가 필요해", "가벼운 → 단백질"),
    ("train", 117): ("저녁을 굶으면 새벽에 폭식하게 되는 편이라 지금 편의점에서 닭가슴살이나 계란처럼 가볍지만 오래 배부른 걸 먹어두고 싶어",
                     "저녁을 굶으면 새벽에 폭식하게 되는 편이라 지금 편의점에서 닭가슴살이나 계란처럼 단백질 많고 오래 배부른 걸 먹어두고 싶어", "가볍지만 → 단백질 많고"),
    ("train", 147): ("요즘 아침을 자꾸 거르게 돼서 오전에 힘이 없고 근육도 빠지는 것 같아 편의점에서 가볍게 먹을 수 있는 영양 있는 아침 대용품을 찾고 있어",
                     "요즘 아침을 자꾸 거르게 돼서 오전에 힘이 없고 근육도 빠지는 것 같아 편의점에서 단백질 챙겨 먹을 수 있는 영양 있는 아침 대용품을 찾고 있어", "가볍게 → 단백질 챙겨"),
    ("train", 221): ("가볍게 먹어도 든든한 간식 알려줘", "단백질 있어서 든든한 간식 알려줘", "가볍게 먹어도 → 단백질 있어서"),
    ("train", 333): ("회사 가기 전에 가볍게 영양 챙길 만한 거 없을까", "회사 가기 전에 단백질 챙길 만한 거 없을까", "가볍게 영양 → 단백질"),
    ("train", 372): ("가볍게 먹는 샐러드에 힘을 더해줄 걸 알고 싶어", "평소 먹는 샐러드에 단백질로 힘을 더해줄 걸 알고 싶어", "가볍게 먹는 → 평소 먹는, 단백질로 추가"),
    # train 나트륨↓+지방↓
    ("train", 462): ("자기 전에 가볍게 입을 달래줄 야식을 추천해줘", "자기 전에 짜지 않게 입을 달래줄 야식을 추천해줘", "가볍게 → 짜지 않게"),
    ("train", 492): ("얼굴 붓는 거 막으려고 가볍게 먹을 걸 찾고 있어", "얼굴 붓는 거 막으려고 싱겁게 먹을 걸 찾고 있어", "가볍게 → 싱겁게"),
    ("train", 513): ("요즘 짠 음식이 입에 안 맞아서 순한 걸 찾고 있어", "요즘 짠 음식이 입에 안 맞아서 싱거운 걸 찾고 있어", "순한 → 싱거운"),
    ("train", 520): ("몸에 부담 없는 순한 간의 음식이 필요해", "몸에 부담 없는 싱거운 간의 음식이 필요해", "순한 → 싱거운"),
    ("train", 522): ("입이 짠맛에 지쳐서 순한 맛으로 먹고 싶어", "입이 짠맛에 지쳐서 담백한 맛으로 먹고 싶어", "순한 → 담백한"),
    ("train", 537): ("입맛이 변했는지 요즘 조금만 짜도 못 먹겠더라 간이 순하면서 먹을 만한 게 편의점에 있을까",
                     "입맛이 변했는지 요즘 조금만 짜도 못 먹겠더라 간이 싱거우면서 먹을 만한 게 편의점에 있을까", "순하면서 → 싱거우면서"),
    ("train", 578): ("술 마신 다음 날 몸을 달래줄 순한 음식을 먹고 싶어", "술 마신 다음 날 몸을 달래줄 짜지 않은 음식을 먹고 싶어", "순한 → 짜지 않은"),
    ("train", 581): ("술 때문에 지친 몸을 추스를 수 있는 순한 음식이 필요해", "술 때문에 지친 몸을 추스를 수 있는 담백한 음식이 필요해", "순한 → 담백한"),
    ("train", 588): ("해장해야댐 순한거 추천점", "해장해야댐 담백한거 추천점", "순한거 → 담백한거"),
    ("train", 612): ("건강검진을 대비해 가볍게 먹을 거 알려줘", "건강검진을 대비해 싱겁게 먹을 거 알려줘", "가볍게 → 싱겁게"),
    ("train", 633): ("어린이집 보낼 간식인데 순한 거 있어", "어린이집 보낼 간식인데 짜지 않은 거 있어", "순한 → 짜지 않은"),
    ("train", 637): ("아이가 먹어도 부담 없는 순한 간의 간식을 찾고 있어", "아이가 먹어도 부담 없는 싱거운 간의 간식을 찾고 있어", "순한 → 싱거운"),
    ("train", 640): ("어릴 때부터 짜게 먹지 않도록 순한 간식을 골라주고 싶어", "어릴 때부터 짜게 먹지 않도록 저염 간식을 골라주고 싶어", "순한 → 저염"),
    ("train", 648): ("아기 간식 순한거 추천점", "아기 간식 안짠거 추천점", "순한거 → 안짠거"),
    ("train", 653): ("아이 간식 5천원 정도로 순한 거 있어", "아이 간식 5천원 정도로 짜지 않은 거 있어", "순한 → 짜지 않은"),
    ("train", 655): ("6천원 이하로 아이용 순한 간식 추천해줘", "6천원 이하로 아이용 저염 간식 추천해줘", "순한 → 저염"),
    ("train", 656): ("다섯 살 아이가 편의점 과자를 자꾸 사 달라고 하는데 짠 과자는 먹이고 싶지 않아서 그나마 간이 순한 걸 사 주려고 해 추천해줘",
                     "다섯 살 아이가 편의점 과자를 자꾸 사 달라고 하는데 짠 과자는 먹이고 싶지 않아서 그나마 간이 싱거운 걸 사 주려고 해 추천해줘", "순한 → 싱거운"),
    ("train", 658): ("아이 간식 순한 거", "아이 간식 안 짠 거", "순한 → 안 짠"),
    ("train", 671): ("신장에 무리 가지 않게 순한 걸로 한 끼 해결하고 싶어", "신장에 무리 가지 않게 저염으로 한 끼 해결하고 싶어", "순한 걸로 → 저염으로"),
    ("train", 687): ("아버지가 신장 투석 전 단계라서 식단 관리를 하고 계시거든 병문안 가는 길에 편의점에서 사 갈 만한 순한 걸 추천해줘",
                     "아버지가 신장 투석 전 단계라서 식단 관리를 하고 계시거든 병문안 가는 길에 편의점에서 사 갈 만한 짜지 않은 걸 추천해줘", "순한 → 짜지 않은"),
    ("train", 691): ("점심에 국물 많은 거 먹어서 저녁은 순하게 먹을래", "점심에 국물 많은 거 먹어서 저녁은 싱겁게 먹을래", "순하게 → 싱겁게"),
    ("train", 692): ("낮에 짠 걸 먹었더니 저녁은 가볍게 하고 싶어", "낮에 짠 걸 먹었더니 저녁은 싱겁게 하고 싶어", "가볍게 → 싱겁게"),
    ("train", 696): ("점심이 너무 자극적이었어 저녁은 순하게 먹고 싶어", "점심이 너무 자극적이었어 저녁은 담백하게 먹고 싶어", "순하게 → 담백하게"),
    ("train", 697): ("낮에 짜게 먹은 걸 저녁에는 가볍게 균형 맞추고 싶어", "낮에 짜게 먹은 걸 저녁에는 싱겁게 균형 맞추고 싶어", "가볍게 → 싱겁게"),
    ("train", 698): ("점심에 먹은 짠맛을 저녁으로 상쇄할 순한 음식을 찾고 있어", "점심에 먹은 짠맛을 저녁으로 상쇄할 저염 음식을 찾고 있어", "순한 → 저염"),
    ("train", 702): ("짠 점심 뒤라 저녁은 순한 맛으로 가고 싶은데 알려줘", "짠 점심 뒤라 저녁은 짜지 않은 맛으로 가고 싶은데 알려줘", "순한 → 짜지 않은"),
    ("train", 709): ("점심 라면먹음 저녁은 순한거로", "점심 라면먹음 저녁은 안짠거로", "순한거로 → 안짠거로"),
    ("train", 712): ("저녁 4천원 안쪽으로 순한 거 골라줘", "저녁 4천원 안쪽으로 저염인 거 골라줘", "순한 → 저염인"),
    ("train", 715): ("7천원 이하로 점심 뒤 저녁 순한 걸로", "7천원 이하로 점심 뒤 저녁 싱거운 걸로", "순한 → 싱거운"),
    ("train", 716): ("오늘 점심 회식으로 짬뽕이랑 짠 반찬을 잔뜩 먹었더니 아직도 속이 짜서 저녁은 편의점에서 간이 순한 걸로 가볍게 먹고 싶어",
                     "오늘 점심 회식으로 짬뽕이랑 짠 반찬을 잔뜩 먹었더니 아직도 속이 짜서 저녁은 편의점에서 간이 싱거운 걸로 담백하게 먹고 싶어", "순한 → 싱거운, 가볍게 → 담백하게"),
    ("train", 718): ("점심 짰어 저녁은 순하게", "점심 짰어 저녁은 싱겁게", "순하게 → 싱겁게"),
    ("train", 757): ("짠맛에 익숙해진 입맛을 순하게 바꾸고 싶어", "짠맛에 익숙해진 입맛을 싱겁게 바꾸고 싶어", "순하게 → 싱겁게"),
    ("train", 762): ("간이 센 음식에서 벗어나려고 하는데 순한 걸 알려줘", "간이 센 음식에서 벗어나려고 하는데 짜지 않은 걸 알려줘", "순한 → 짜지 않은"),
    ("train", 769): ("나 너무 짜게먹음 순한거 알려줘", "나 너무 짜게먹음 안짠거 알려줘", "순한거 → 안짠거"),
    ("train", 775): ("7천원 이하로 순한 거 알려줘", "7천원 이하로 저염인 거 알려줘", "순한 → 저염인"),
    ("train", 777): ("평소에 국물까지 다 먹고 간이 센 음식을 좋아해서 이제 습관을 고치려는데 편의점에서 쉽게 살 수 있는 순한 음식이 뭐가 있는지 알려줘",
                     "평소에 국물까지 다 먹고 간이 센 음식을 좋아해서 이제 습관을 고치려는데 편의점에서 쉽게 살 수 있는 싱거운 음식이 뭐가 있는지 알려줘", "순한 → 싱거운"),
    ("train", 811): ("부모님이 짜게 드시는 걸 줄이셔야 해서 순한 걸로 고르고 싶어", "부모님이 짜게 드시는 걸 줄이셔야 해서 싱거운 걸로 고르고 싶어", "순한 → 싱거운"),
    ("train", 814): ("아빠가 짠 걸 조심하라고 해서 순한 거 알려줘", "아빠가 짠 걸 조심하라고 해서 짜지 않은 거 알려줘", "순한 → 짜지 않은"),
    ("train", 819): ("부모님이 짜게 드시지 않도록 순한 맛으로 골라드리고 싶어", "부모님이 짜게 드시지 않도록 담백한 맛으로 골라드리고 싶어", "순한 → 담백한"),
    ("train", 820): ("어르신 입맛에 맞는 순한 간의 음식을 알려줘", "어르신 입맛에 맞는 싱거운 간의 음식을 알려줘", "순한 → 싱거운"),
    ("train", 829): ("어르신 순한간식 알려줘", "어르신 저염간식 알려줘", "순한간식 → 저염간식"),
    ("train", 832): ("부모님 간식 4천원 안쪽으로 순한 걸로", "부모님 간식 4천원 안쪽으로 짜지 않은 걸로", "순한 → 짜지 않은"),
    ("train", 834): ("3천원대로 어르신이 드실 순한 거", "3천원대로 어르신이 드실 싱거운 거", "순한 → 싱거운"),
    ("train", 836): ("아버지가 혈압 때문에 짜게 드시면 안 되는데 병문안 갈 때 편의점에서 사 가려고 하거든 간이 순한 걸로 알려줘",
                     "아버지가 혈압 때문에 짜게 드시면 안 되는데 병문안 갈 때 편의점에서 사 가려고 하거든 간이 싱거운 걸로 알려줘", "순한 → 싱거운"),
    ("train", 839): ("부모님 순한 간식", "부모님 저염 간식", "순한 → 저염"),
    ("train", 841): ("몸이 붓는 느낌이라 가볍게 먹고 싶어", "몸이 붓는 느낌이라 싱겁게 먹고 싶어", "가볍게 → 싱겁게"),
    ("train", 848): ("붓는 느낌을 가라앉힐 수 있는 가벼운 음식이 필요해", "붓는 느낌을 가라앉힐 수 있는 짜지 않은 음식이 필요해", "가벼운 → 짜지 않은"),
    ("train", 852): ("붓기가 빠지는 데 도움 되는 순한 음식을 알려줘", "붓기가 빠지는 데 도움 되는 싱거운 음식을 알려줘", "순한 → 싱거운"),
    # train 탄수화물↑+열량↑
    ("train", 972): ("오전 시험 전에 탄수화물 위주로 가볍게 먹고 싶어요.", "오전 시험 전에 탄수화물 위주로 챙겨 먹고 싶어요.", "가볍게 → 챙겨"),
    # train 탄수화물↓+단백질↑
    ("train", 1163): ("오늘 3500원으로 가볍게 먹고 졸음을 피하고 싶어.", "오늘 3500원으로 밥이나 면 없이 먹고 졸음을 피하고 싶어.", "가볍게 → 밥이나 면 없이"),
    ("train", 1287): ("낮에 친구가 파스타를 사줘서 양껏 먹었는데 저녁 약속은 없고, 집에 가는 길에 편의점에서 가볍게 면이나 밥이 아닌 걸 사 가려고 해요.",
                      "낮에 친구가 파스타를 사줘서 양껏 먹었는데 저녁 약속은 없고, 집에 가는 길에 편의점에서 면이나 밥이 아닌 걸 사 가려고 해요.", "가볍게 삭제 (단서 '면이나 밥이 아닌'은 이미 있음)"),
}
AMBIGUOUS = {
    ("train", 458): "몸이 가벼운: 다음 날 몸 상태인지 음식의 가벼움인지 모호",
    ("train", 1751): "S2033 지방↓+열량↓: 둘째 영양소가 열량↓이라 열량 단서와 겹침",
    ("train", 2818): "가볍게 사고: 구매 행동을 꾸미는지 음식의 가벼움인지 모호",
}
UNRELATED = {("train", 1347): "몸이 가벼워졌다고: 몸 상태 (음식과 무관)"}


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def read(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def write(rows, p):
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def is_cal_low(r):
    return (r["성분1"], r["방향1"]) == ("열량", "낮음")


def main(dev_p, train_p, out):
    md5_in = {"dev_v2": md5(dev_p), "train_v2": md5(train_p)}
    v2 = {"dev": read(dev_p), "train": read(train_p)}
    v3 = {k: [dict(r) for r in v] for k, v in v2.items()}

    # 대상 목록과 분류가 빠짐없이 일치하는지 확인
    hits = {(s, i) for s in v2 for i, r in enumerate(v2[s]) if PAT.search(r["입력 문장"]) and not is_cal_low(r)}
    classified = set(EDITS) | set(AMBIGUOUS) | set(UNRELATED)
    assert hits == classified, {"unclassified": sorted(hits - classified), "extra": sorted(classified - hits)}

    log, amb = [], []
    for (s, i), (old, new, expr) in EDITS.items():
        r = v3[s][i]
        assert r["입력 문장"] == old, (s, i, r["입력 문장"])
        r["입력 문장"] = new
        log.append({"세트": s, "상황ID": r["상황ID"], "이전 문장": old, "수정한 문장": new, "바뀐 표현": expr})
    for (s, i), why in AMBIGUOUS.items():
        r = v2[s][i]
        amb.append({"세트": s, "상황ID": r["상황ID"], "문장": r["입력 문장"], "남긴 이유": why})

    write(v3["dev"], os.path.join(out, "dev_pair_v3.csv"))
    write(v3["train"], os.path.join(out, "train_pair_v3.csv"))
    with open(os.path.join(out, "수정내역_v3.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["세트", "상황ID", "이전 문장", "수정한 문장", "바뀐 표현"])
        w.writeheader()
        w.writerows(sorted(log, key=lambda x: (x["세트"], x["상황ID"])))
    with open(os.path.join(out, "애매_목록_v3.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["세트", "상황ID", "문장", "남긴 이유"])
        w.writeheader()
        w.writerows(amb)

    # 3단계 검증 (쓴 파일을 다시 읽어서)
    d, t = read(os.path.join(out, "dev_pair_v3.csv")), read(os.path.join(out, "train_pair_v3.csv"))
    C = {}

    def add(k, ok, detail):
        C[k] = {"ok": bool(ok), "detail": detail}

    hdr = {n: list(read(os.path.join(out, f"{n}_pair_v3.csv"))[0].keys()) for n in ("dev", "train")}
    add("rows_and_columns", len(d) == 216 and len(t) == 2820 and all(h == COLS for h in hdr.values()),
        {"dev": len(d), "train": len(t), "columns_ok": all(h == COLS for h in hdr.values())})
    same_lab = all(a[k] == b[k] for s, new in (("dev", d), ("train", t)) for a, b in zip(v2[s], new)
                   for k in LABELS + ["상황ID", "말투 유형", "작성자"])
    add("labels_identical_to_v2", same_lab and len(v2["dev"]) == len(d) and len(v2["train"]) == len(t),
        "성분1·방향1·성분2·방향2(+상황ID·말투 유형·작성자) 전부 v2와 동일" if same_lab else "다름")
    changed = {s: sum(a["입력 문장"] != b["입력 문장"] for a, b in zip(v2[s], new)) for s, new in (("dev", d), ("train", t))}
    add("only_listed_sentences_changed", changed == {s: sum(1 for k in EDITS if k[0] == s) for s in ("dev", "train")}, changed)
    dup = {n: [x for x, c in collections.Counter(r["입력 문장"].strip() for r in rows).items() if c > 1]
           for n, rows in (("dev", d), ("train", t))}
    cross = sorted({r["입력 문장"].strip() for r in d} & {r["입력 문장"].strip() for r in t})
    sit_cross = sorted({r["상황ID"] for r in d} & {r["상황ID"] for r in t})
    add("no_dup_no_overlap", not dup["dev"] and not dup["train"] and not cross and not sit_cross,
        {"dup": dup, "sentence_overlap": cross, "situation_overlap": sit_cross})
    add("rule_situations_not_in_dev", not ({r["상황ID"] for r in d} & set(RULE_SITS)),
        sorted({r["상황ID"] for r in d} & set(RULE_SITS)))
    remain = [{"세트": n, "상황ID": r["상황ID"], "문장": r["입력 문장"],
               "분류": "음식과 무관" if (n, i) in UNRELATED else "애매"}
              for n, rows in (("dev", d), ("train", t)) for i, r in enumerate(rows)
              if PAT.search(r["입력 문장"]) and not is_cal_low(r)]
    allowed = set(AMBIGUOUS) | set(UNRELATED)
    remain_keys = {(n, i) for n, rows in (("dev", d), ("train", t)) for i, r in enumerate(rows)
                   if PAT.search(r["입력 문장"]) and not is_cal_low(r)}
    add("remaining_pattern_outside_cal_low", remain_keys == allowed, remain)
    cal_words = re.compile("열량|칼로리|저열량|kcal")
    new_cal = [x["수정한 문장"] for x in log if cal_words.search(x["수정한 문장"]) and not cal_words.search(x["이전 문장"])]
    add("no_new_calorie_words", not new_cal, new_cal)
    md5_after = {"dev_v2": md5(dev_p), "train_v2": md5(train_p)}
    add("v2_inputs_unchanged", md5_in == md5_after, md5_after)

    per = collections.Counter((x["세트"], x["상황ID"]) for x in log)
    res = {"inputs_md5": md5_in,
           "outputs_md5": {f: md5(os.path.join(out, f)) for f in ("dev_pair_v3.csv", "train_pair_v3.csv")},
           "checks": C, "edits_total": len(log),
           "edits_by_set": dict(collections.Counter(x["세트"] for x in log)),
           "edits_by_situation": {f"{s} {k}": v for (s, k), v in sorted(per.items())},
           "kept_cal_low": {s: sum(1 for r in v2[s] if PAT.search(r["입력 문장"]) and is_cal_low(r)) for s in v2},
           "ambiguous": len(amb), "unrelated": len(UNRELATED),
           "all_ok": all(v["ok"] for v in C.values())}
    json.dump(res, open(os.path.join(out, "v3_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(0 if res["all_ok"] else 1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
