"""이전 prompt.txt의 시스템 프롬프트와 복사한 스크립트의 SYSTEM_PROMPT를 sha256으로 비교. 다르면 exit 1.
usage: python hash_prompt.py <prev_prompt_txt> <script_py>
"""
import hashlib
import importlib.util
import sys

prev = open(sys.argv[1], encoding="utf-8").read()
prev_sys = prev.split("[system prompt]\n", 1)[1].split("\n\n[rendered chat template]\n", 1)[0]
spec = importlib.util.spec_from_file_location("m", sys.argv[2])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
a = hashlib.sha256(prev_sys.encode("utf-8")).hexdigest()
b = hashlib.sha256(m.SYSTEM_PROMPT.encode("utf-8")).hexdigest()
print("prev_system_prompt_sha256", a)
print("this_system_prompt_sha256", b)
print("SAME" if a == b else "DIFFERENT")
sys.exit(0 if a == b else 1)
