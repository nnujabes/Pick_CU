"""filter_engine.recommend를 실제 cu_products.db와 임시 DB로 시험한다."""
import hashlib
import itertools
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pickcu.filter_engine as fe  # noqa: E402
from pickcu.filter_engine import recommend  # noqa: E402
from pickcu.product_search import DB_PATH  # noqa: E402

digest = lambda: hashlib.md5(DB_PATH.read_bytes()).hexdigest()
before = digest()
passed = 0
HP_LS = {'단백질': 'high', '당류': 'low'}


def check(name, condition):
    global passed
    print(('통과 ' if condition else '실패 ') + name)
    if not condition:
        raise SystemExit(1)
    passed += 1


def raises(error, *args, **kwargs):
    try:
        recommend(*args, **kwargs)
    except error:
        return True
    return False


def ids(results):
    return [tuple(i['item_cd'] for i in r['items']) for r in results]


def independent_top5(categories, nutrients, budget, nutrition_only=False):
    """엔진 함수를 쓰지 않고 정의대로 직접 계산한다."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute('SELECT * FROM cu_products')]
    con.close()
    pools = []
    score = {}
    for category in categories:
        pool = [r for r in rows if r['category'] == category and (budget is None or r['price'] <= budget)]
        pools.append(pool)
        for r in pool:
            parts = []
            for column, direction in nutrients.items():
                values = [x[column] for x in pool]
                less = sum(v < r[column] for v in values)
                equal = sum(v == r[column] for v in values)
                pct = (less + equal / 2) / len(values) * 100
                parts.append(pct if direction == 'high' else 100 - pct)
            score[r['item_cd']] = sum(parts) / len(parts)
    combos = []
    for picks in itertools.product(*pools):
        total = sum(p['price'] for p in picks)
        if budget is not None and total > budget:
            continue
        nutrition = sum(score[p['item_cd']] for p in picks) / len(picks)
        final = nutrition if nutrition_only else 0.7 * nutrition + 0.3 * total / budget * 100
        combos.append((-round(final, 6), -round(nutrition, 6), total, tuple(p['item_cd'] for p in picks)))
    combos.sort()
    chosen, used = [], set()
    for combo in combos:
        if used & set(combo[3]):
            continue
        chosen.append(combo[3])
        used |= set(combo[3])
        if len(chosen) == 5:
            break
    return chosen


# 1. 시연 질문
scenario = recommend(['간편식사', '음료'], HP_LS, budget=10000)
columns = {'protein': 'high', 'sugar': 'low'}
check('시연 질문: 직접 계산한 Top 5와 일치', ids(scenario) == independent_top5(['간편식사', '음료'], columns, 10000))
check('5개 반환, 순위 1~5', [r['rank'] for r in scenario] == [1, 2, 3, 4, 5])
check('합계가 예산 이하', all(r['total_price'] <= 10000 for r in scenario))
check('합계가 상품 가격의 합', all(r['total_price'] == sum(i['price'] for i in r['items']) for r in scenario))
check('카테고리마다 1개씩', all([i['category'] for i in r['items']] == ['간편식사', '음료'] for r in scenario))
flat = [c for pair in ids(scenario) for c in pair]
check('Top 5 안에 상품 중복 없음', len(flat) == len(set(flat)))
check('총점 내림차순', all(a['total_score'] >= b['total_score'] for a, b in zip(scenario, scenario[1:])))
check('7:3 계산식 일치', all(abs(r['total_score'] - (0.7 * r['nutrition_score'] + 0.3 * r['price_score'])) < 0.11 for r in scenario))
check('가격 점수 = 합계 ÷ 예산 × 100', all(abs(r['price_score'] - r['total_price'] / 100) < 0.051 for r in scenario))
check('화면용 항목 포함(행사, 이미지, 영양소)', all({'event_type', 'thumbnail_url', 'product_name', 'protein', 'nutrition_score'} <= set(i) for r in scenario for i in r['items']))

# 2. 가격 점수를 쓰지 않는 경우
no_budget = recommend(['즉석조리', '음료'], HP_LS)
check('금액 없음: 직접 계산과 일치', ids(no_budget) == independent_top5(['즉석조리', '음료'], columns, None, nutrition_only=True))
check('금액 없음: 영양 점수만 사용', all(r['price_score'] is None and r['total_score'] == r['nutrition_score'] for r in no_budget))
single = recommend(['음료'], HP_LS, budget=3000)
check('카테고리 1개: 직접 계산과 일치', ids(single) == independent_top5(['음료'], columns, 3000, nutrition_only=True))
check('카테고리 1개: 영양 점수만, 단일 상품, 예산 이하', all(r['price_score'] is None and len(r['items']) == 1 and r['total_price'] <= 3000 for r in single))

# 3. 카테고리 3개
three = recommend(['간편식사', '과자류', '음료'], HP_LS, budget=10000)
check('카테고리 3개: 상품 3개 조합 5개, 중복 없음', len(three) == 5 and all(len(r['items']) == 3 for r in three) and len({c for t in ids(three) for c in t}) == 15)
low = recommend(['간편식사', '과자류', '음료'], HP_LS, budget=3000)
check('카테고리 3개 낮은 예산(3,000원)에서도 결과 있음', len(low) > 0 and all(r['total_price'] <= 3000 for r in low))

# 4. 결과 부족, 없음
check('결과 없음은 빈 리스트(재질문용)', recommend(['식품'], HP_LS, budget=1) == [])
check('카테고리 하나라도 후보가 없으면 빈 리스트', recommend(['간편식사', '음료'], HP_LS, budget=1000) == [])
check('예산 안 상품이 1개면 1개만 반환', len(recommend(['즉석조리'], HP_LS, budget=1000)) == 1)

# 5. 잘못된 입력
check('영양소 조건 없음 거부', raises(ValueError, ['음료'], {}))
check('없는 영양소 거부', raises(ValueError, ['음료'], {'비타민': 'high'}))
check('high/low 외 값 거부', raises(ValueError, ['음료'], {'단백질': 'medium'}))
check('영양소가 딕셔너리가 아니면 거부', raises(TypeError, ['음료'], ['단백질']))
check('잘못된 카테고리 거부', raises(ValueError, ['식사'], HP_LS))
check('카테고리 4개 거부', raises(ValueError, ['간편식사', '즉석조리', '과자류', '음료'], HP_LS))
check('문자열 예산 거부', raises(ValueError, ['음료'], HP_LS, budget='10000'))

# 6. 동점 처리
def combo(total, nutrition, price, cds):
    return (fe.rank_key(total, nutrition, price, cds), None, total, nutrition, None, price)

ordered = fe.select_top([
    combo(80, 70, 9000, ('a',)),
    combo(80, 90, 7000, ('b',)),
    combo(80, 90, 6000, ('d',)),
    combo(80, 90, 6000, ('c',)),
    combo(85, 10, 1000, ('e',)),
])
check('동점: 총점 → 영양 점수 → 낮은 합계 → 바코드', [c[0][3][0] for c in ordered] == ['e', 'c', 'd', 'b', 'a'])
check('소수 오차는 동점으로 처리', fe.rank_key(80.00000000001, 1, 1, ('a',))[0] == fe.rank_key(80, 1, 1, ('a',))[0])

# 7. 임시 DB: 중복 금지로 5개를 못 채우는 경우, 같은 값의 점수
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'small.db'
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE cu_products (item_cd TEXT, category TEXT, product_name TEXT, price INT, event_type TEXT, calories REAL, protein REAL, sodium REAL, carbs REAL, sugar REAL, fat REAL, thumbnail_url TEXT)')
    rows = [('m1', '간편식사', 3000, 30), ('m2', '간편식사', 3000, 10), ('d1', '음료', 1000, 20), ('d2', '음료', 1000, 5)]
    con.executemany("INSERT INTO cu_products VALUES (?,?,?,?,'1+1',0,?,0,0,0,0,'u')", [(c, cat, c, p, v) for c, cat, p, v in rows])
    con.commit()
    con.close()
    small = recommend(['간편식사', '음료'], {'단백질': 'high'}, budget=10000, db_path=path)
    check('중복 금지로 조합이 부족하면 있는 만큼만 반환', ids(small) == [('m1', 'd1'), ('m2', 'd2')])
    check('행사 정보는 그대로 전달하고 가격은 정가 합계', small[0]['items'][0]['event_type'] == '1+1' and small[0]['total_price'] == 4000)
    high = fe.score_items([{'item_cd': 'x', 'protein': 1.0}, {'item_cd': 'y', 'protein': 1.0}, {'item_cd': 'z', 'protein': 3.0}], {'단백질': 'high'})
    lows = fe.score_items([{'item_cd': 'x', 'protein': 1.0}, {'item_cd': 'y', 'protein': 1.0}, {'item_cd': 'z', 'protein': 3.0}], {'단백질': 'low'})
    check('백분위: 같은 값은 같은 점수, low는 뒤집힘', high['x'] == high['y'] < high['z'] and abs(lows['x'] + high['x'] - 100) < 1e-9)

check('DB 파일 변경 없음', digest() == before)
print(f'\n시험 {passed}개 통과')


# 8. 후보 줄이기 손실: 전체 조합과 비교
def compare_reduction(categories, budget, nutrients):
    reduced = recommend(categories, nutrients, budget=budget)
    original = fe.reduce_candidates
    fe.reduce_candidates = lambda items, scores: items
    started = time.time()
    full = recommend(categories, nutrients, budget=budget)
    elapsed = time.time() - started
    fe.reduce_candidates = original
    avg = lambda rs: sum(r['total_score'] for r in rs) / len(rs)
    same = len(set(ids(reduced)) & set(ids(full)))
    print(f"{'+'.join(categories)} {budget:,}원: 줄임 평균 총점 {avg(reduced):.1f} / 전체 {avg(full):.1f}, 1위 같음 {ids(reduced)[0] == ids(full)[0]}, 같은 조합 {same}/5, 전체 계산 {elapsed:.1f}초")


print('\n[후보 줄이기 손실]')
compare_reduction(['즉석조리', '아이스크림', '음료'], 10000, HP_LS)
compare_reduction(['즉석조리', '아이스크림', '음료'], 5000, HP_LS)
compare_reduction(['즉석조리', '아이스크림', '음료'], 7000, {'당류': 'low', '열량': 'low'})

print('\n[실행 시간]')
for label, args, kwargs in (
    ('2개 최대(식품+과자류, 금액 없음)', (['식품', '과자류'], HP_LS), {}),
    ('3개(식품+과자류+음료, 금액 없음)', (['식품', '과자류', '음료'], HP_LS), {}),
):
    started = time.time()
    recommend(*args, **kwargs)
    print(label, f'{time.time() - started:.2f}초')


def show(title, results):
    print(f'\n[{title}] {len(results)}개')
    for r in results:
        names = ' + '.join(f"{i['product_name']}({i['price']:,}{'' if i['event_type'] == 'NONE' else ' ' + i['event_type']})" for i in r['items'])
        print(f"  {r['rank']}. 총점 {r['total_score']} 영양 {r['nutrition_score']} 가격 {r['price_score']} 합계 {r['total_price']:,}원 / {names}")


show('시연: 간편식사+음료 1만 원, 단백질↑ 당류↓', scenario)
show('금액 없음: 간편식사+음료, 단백질↑ 당류↓', recommend(['간편식사', '음료'], HP_LS))
show('1개: 음료 3천 원, 단백질↑ 당류↓', single)
show('3개: 간편식사+과자류+음료 1만 원, 단백질↑ 당류↓', three)
