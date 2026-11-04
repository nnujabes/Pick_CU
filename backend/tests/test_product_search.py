"""product_search.search_candidates를 실제 cu_products.db로 시험한다."""
import hashlib
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pickcu.product_search import CATEGORIES, DB_PATH, search_candidates  # noqa: E402

EXPECTED_TOTAL = {'간편식사': 199, '즉석조리': 40, '과자류': 627, '아이스크림': 109, '식품': 768, '음료': 411}
KEYS = ['item_cd', 'category', 'product_name', 'price', 'event_type', 'calories', 'protein', 'sodium', 'carbs', 'sugar', 'fat', 'thumbnail_url']
digest = lambda: hashlib.md5(DB_PATH.read_bytes()).hexdigest()
before = digest()
passed = 0


def check(name, condition):
    global passed
    print(('통과 ' if condition else '실패 ') + name)
    if not condition:
        raise SystemExit(1)
    passed += 1


def raises(error, *args, **kwargs):
    try:
        search_candidates(*args, **kwargs)
    except error:
        return True
    return False


# 대조용 전체 데이터는 함수와 별개로 읽는다
con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute('SELECT * FROM cu_products')]
con.close()

all_result = search_candidates(list(CATEGORIES)[:3])
check('예산 없음: 가격 제한 없이 카테고리 전체', {k: len(v) for k, v in all_result.items()} == {k: EXPECTED_TOTAL[k] for k in list(CATEGORIES)[:3]})
for c in CATEGORIES:
    assert len(search_candidates([c])[c]) == EXPECTED_TOTAL[c]
check('카테고리 6개 각각 전체 건수 일치', True)

result = search_candidates(['간편식사', '음료'], budget=10000)
check('요청한 카테고리만 반환', list(result) == ['간편식사', '음료'])
for c, items in result.items():
    expected = {r['item_cd'] for r in rows if r['category'] == c and r['price'] <= 10000}
    assert {i['item_cd'] for i in items} == expected and all(i['category'] == c for i in items)
check('예산 1만 원: 대조 데이터와 같은 상품 (10,000원 이하)', True)
check('가격 오름차순', all([i['price'] for i in v] == sorted(i['price'] for i in v) for v in result.values()))
check('상품 컬럼 12개', all(list(i) == KEYS for v in result.values() for i in v))
check('dict로 반환되고 숫자 타입 유지', isinstance(result['음료'][0]['price'], int) and isinstance(result['음료'][0]['protein'], float))

# 경계값: 실제 있는 가격에서 확인
price = sorted({r['price'] for r in rows if r['category'] == '음료'})[len({r['price'] for r in rows if r['category'] == '음료'}) // 2]
at = search_candidates(['음료'], budget=price)['음료']
below = search_candidates(['음료'], budget=price - 1)['음료']
check(f'경계값 {price}원: 같은 가격 포함, 1원 낮으면 제외', any(i['price'] == price for i in at) and all(i['price'] < price for i in below))
check('margin 인자 제거됨', raises(TypeError, ['음료'], budget=price, margin=500))
check('후보 없음은 빈 리스트', search_candidates(['식품'], budget=1) == {'식품': []})

check('카테고리 0개 거부', raises(ValueError, []))
check('카테고리 4개 거부', raises(ValueError, list(CATEGORIES)[:4]))
check('중복 거부', raises(ValueError, ['음료', '음료']))
check('없는 카테고리 거부', raises(ValueError, ['식사']))
check('문자열 카테고리 거부', raises(TypeError, '음료'))
check('SQL 주입 문자열 거부', raises(ValueError, ["음료' OR '1'='1"]))
for bad in (0, -1000, '10000', 1.5, True):
    assert raises(ValueError, ['음료'], budget=bad), bad
check('잘못된 budget 거부', True)
check('DB 없으면 FileNotFoundError', raises(FileNotFoundError, ['음료'], db_path='/nonexistent/x.db'))
with tempfile.TemporaryDirectory() as tmp:
    missing = Path(tmp) / 'none.db'
    raises(FileNotFoundError, ['음료'], db_path=missing)
    check('없는 DB 파일을 새로 만들지 않음', not missing.exists())

# 읽기 전용 확인
try:
    c = sqlite3.connect(f'{DB_PATH.as_uri()}?mode=ro', uri=True)
    c.execute("DELETE FROM cu_products")
    readonly = False
except sqlite3.OperationalError:
    readonly = True
finally:
    c.close()
check('읽기 전용 연결은 쓰기 불가', readonly)
check('DB 파일 변경 없음', digest() == before)
print(f'\n시험 {passed}개 통과')

print('\n[시나리오] 간편식사 + 음료, 예산 10,000원')
for c, items in result.items():
    print(c, f'후보 {len(items)}개, 가격 {items[0]["price"]}~{items[-1]["price"]}원')
    for i in items[:2]:
        print('  ', i['product_name'], i['price'], i['event_type'], f"단백질 {i['protein']:g}g 당류 {i['sugar']:g}g")
