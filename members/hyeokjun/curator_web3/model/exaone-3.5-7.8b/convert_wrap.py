"""EXAONE 3.5 변환용: transformers 5가 원격 코드 없이 rope_scaling을 다룰 때 나는 오류만 피하고 llama.cpp 변환기를 그대로 실행한다."""
import os, runpy, sys
G = os.path.expanduser('~/pickcu_gguf/llama.cpp')
sys.path.insert(0, G)
from transformers.configuration_utils import PreTrainedConfig
PreTrainedConfig.max_position_embeddings = 32768
sys.argv[0] = os.path.join(G, 'convert_hf_to_gguf.py')
runpy.run_path(sys.argv[0], run_name='__main__')
